"""Ticket service operations."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import frontmatter
from filelock import FileLock

from karya.core.filesystem import (
	KARYA_ROOT,
	TICKET_DIRS,
	append_event,
	find_ticket_path,
	generate_ticket_id,
	init_karya,
	list_tickets_in_state,
	move_ticket,
	normalize_root,
	write_ticket_file,
)
from karya.core.models import Event, Priority, Ticket, TicketStatus, TicketType
from karya.core.parser import parse_ticket, serialize_ticket
from karya.core.state import validate_transition
from karya.core.validator import validate_completable, validate_ticket
from karya.exceptions import (
	IncompleteAcceptanceCriteria,
	InvalidTransitionError,
	TicketNotFoundError,
	UpdateForbiddenError,
	ValidationError,
)
from karya.git.integration import GitIntegration
from karya.services.index_service import IndexService

_UPDATE_FIELDS = {
	"title",
	"priority",
	"labels",
	"agents_allowed",
	"estimated_effort",
	"epic",
	"sprint",
	"owner",
	"dependencies",
	"blocked_by",
	"agent_instructions",
	"linked_adrs",
}

_PRIORITY_ORDER = {
	Priority.CRITICAL: 0,
	Priority.HIGH: 1,
	Priority.MEDIUM: 2,
	Priority.LOW: 3,
}


class TicketService:
	def __init__(self, root: Path):
		self.root = normalize_root(root)
		self._git = GitIntegration(root)
		self._index = IndexService(root)

	def create(
		self,
		title: str,
		context: str = "",
		type: TicketType = TicketType.FEATURE,
		priority: Priority = Priority.MEDIUM,
		epic: str | None = None,
		labels: list[str] | None = None,
		agents_allowed: list[str] | None = None,
		estimated_effort: int = 1,
		actor: str | None = None,
	) -> Ticket:
		init_karya(self.root)

		ticket_id = generate_ticket_id(self.root)
		now = datetime.now(timezone.utc)
		ticket = Ticket(
			id=ticket_id,
			title=title,
			status=TicketStatus.BACKLOG,
			type=type,
			priority=priority,
			created_at=now,
			updated_at=now,
			epic=epic,
			labels=labels or [],
			agents_allowed=agents_allowed or [],
			estimated_effort=estimated_effort,
			context_text=context,
		)

		errors = validate_ticket(ticket)
		if errors:
			raise ValidationError("; ".join(errors))

		path = self.root / TICKET_DIRS[TicketStatus.BACKLOG.value] / f"{ticket_id}.md"
		ticket.path = path
		self._write_ticket(ticket)

		append_event(
			Event(event="ticket_created", ticket_id=ticket_id, actor=actor),
			self.root,
		)
		self._git.commit(f"[{ticket_id}] created ({actor or "system"})")
		return ticket

	def get(self, ticket_id: str) -> Ticket:
		path = find_ticket_path(ticket_id, self.root)
		if not path:
			raise TicketNotFoundError(f"Ticket '{ticket_id}' not found.")
		return parse_ticket(path)

	def list(
		self,
		status: str | None = None,
		agent: str | None = None,
		epic: str | None = None,
		label: str | None = None,
	) -> list[Ticket]:
		statuses = [status] if status else list(TICKET_DIRS.keys())
		tickets: list[Ticket] = []

		for state in statuses:
			for path in list_tickets_in_state(state, self.root):
				tickets.append(parse_ticket(path))

		if agent:
			tickets = [ticket for ticket in tickets if ticket.owner == agent]
		if epic:
			tickets = [ticket for ticket in tickets if ticket.epic == epic]
		if label:
			tickets = [ticket for ticket in tickets if label in ticket.labels]

		return tickets

	def transition(self, ticket_id: str, new_status: str, actor: str | None = None) -> Ticket:
		ticket = self.get(ticket_id)
		current_status = ticket.status.value

		validate_transition(current_status, new_status)

		if new_status == TicketStatus.DONE.value:
			unchecked = validate_completable(ticket)
			if unchecked:
				raise IncompleteAcceptanceCriteria(unchecked)

		if not ticket.path:
			raise TicketNotFoundError(f"Ticket '{ticket_id}' path missing.")

		new_path = move_ticket(ticket.path, new_status, self.root)
		ticket.status = TicketStatus(new_status)
		ticket.path = new_path

		errors = validate_ticket(ticket)
		if errors:
			raise ValidationError("; ".join(errors))

		self._write_ticket(ticket)

		append_event(
			Event(
				event="ticket_transitioned",
				ticket_id=ticket_id,
				actor=actor,
				data={"from": current_status, "to": new_status},
			),
			self.root,
		)
		self._git.commit(f"[{ticket_id}] {current_status} → {new_status} ({actor or "system"})")
		return ticket

	def update(self, ticket_id: str, updates: dict, actor: str | None = None) -> Ticket:
		forbidden = [field for field in updates if field not in _UPDATE_FIELDS]
		if forbidden:
			raise UpdateForbiddenError(
				f"Updates not allowed for fields: {', '.join(forbidden)}"
			)

		ticket = self.get(ticket_id)
		for field, value in updates.items():
			setattr(ticket, field, value)

		errors = validate_ticket(ticket)
		if errors:
			raise ValidationError("; ".join(errors))

		self._write_ticket(ticket)
		append_event(
			Event(
				event="ticket_updated",
				ticket_id=ticket_id,
				actor=actor,
				data={"updates": updates},
			),
			self.root,
		)
		self._git.commit(f"[{ticket_id}] updated ({actor or "system"})")
		return ticket

	def log(self, ticket_id: str, message: str, actor: str | None = None) -> Ticket:
		ticket = self.get(ticket_id)
		entry = {
			"timestamp": datetime.now(timezone.utc).isoformat(),
			"message": message,
			"actor": actor,
		}
		ticket.execution_log.append(entry)
		self._write_ticket(ticket)

		append_event(
			Event(
				event="ticket_logged",
				ticket_id=ticket_id,
				actor=actor,
				data={"message": message},
			),
			self.root,
		)
		self._git.commit(
			f"[{ticket_id}] log entry #{len(ticket.execution_log)} ({actor or "system"})"
		)
		return ticket

	def assign(self, ticket_id: str, agent: str, actor: str | None = None) -> Ticket:
		lock_path = self.root / KARYA_ROOT / "locks" / f"{ticket_id}.lock"
		lock_path.parent.mkdir(parents=True, exist_ok=True)

		with FileLock(str(lock_path)):
			ticket = self.get(ticket_id)
			ticket.owner = agent
			self._write_ticket(ticket)

		append_event(
			Event(
				event="ticket_assigned",
				ticket_id=ticket_id,
				actor=actor,
				data={"agent": agent},
			),
			self.root,
		)
		self._git.commit(f"[{ticket_id}] assigned ({actor or "system"})")
		return ticket

	def block(self, ticket_id: str, reason: str, actor: str | None = None) -> Ticket:
		ticket = self.transition(ticket_id, TicketStatus.BLOCKED.value, actor=actor)
		self.log(ticket_id, f"Blocked: {reason}", actor=actor)
		return ticket

	def link_adr(self, ticket_id: str, adr_id: str, actor: str | None = None) -> Ticket:
		ticket = self.get(ticket_id)
		if adr_id not in ticket.linked_adrs:
			ticket.linked_adrs.append(adr_id)
		self._write_ticket(ticket)

		append_event(
			Event(
				event="ticket_adr_linked",
				ticket_id=ticket_id,
				actor=actor,
				data={"adr_id": adr_id},
			),
			self.root,
		)
		self._git.commit(f"[{ticket_id}] linked adr {adr_id} ({actor or "system"})")
		return ticket

	def get_next(self, agent: str) -> Ticket | None:
		tickets = [
			parse_ticket(path)
			for path in list_tickets_in_state(TicketStatus.TODO.value, self.root)
		]
		candidates: list[Ticket] = []
		for ticket in tickets:
			if ticket.owner:
				continue
			if ticket.agents_allowed and agent not in ticket.agents_allowed:
				continue
			if not self._dependencies_done(ticket):
				continue
			candidates.append(ticket)

		if not candidates:
			return None

		candidates.sort(
			key=lambda item: (
				_PRIORITY_ORDER[item.priority],
				item.estimated_effort,
				item.created_at,
			)
		)
		return candidates[0]

	def describe(self, ticket_id: str) -> dict:
		ticket = self.get(ticket_id)
		data = ticket.model_dump(mode="json")
		if ticket.path:
			data["path"] = str(ticket.path)
		return data

	def _dependencies_done(self, ticket: Ticket) -> bool:
		for dependency in ticket.dependencies:
			path = find_ticket_path(dependency, self.root)
			if not path:
				return False
			dependency_ticket = parse_ticket(path)
			if dependency_ticket.status != TicketStatus.DONE:
				return False
		return True

	def _write_ticket(self, ticket: Ticket) -> None:
		serialized = serialize_ticket(ticket)
		post = frontmatter.loads(serialized)
		if not ticket.path:
			raise TicketNotFoundError("Ticket path missing.")
		write_ticket_file(ticket.path, post.metadata, post.content)
		self._index.update_entity("ticket", ticket.id)
