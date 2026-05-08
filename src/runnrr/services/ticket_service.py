"""Ticket service operations."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from runnrr.core.filesystem import (
	TICKET_DIRS,
	find_ticket_path,
	generate_id,
	init_runnrr,
	list_tickets_in_state,
	move_ticket,
	normalize_root,
	write_file,
)
from runnrr.core.models import Priority, Ticket, TicketStatus, TicketType, normalize_tag
from runnrr.core.parser import parse_ticket, serialize_ticket
from runnrr.core.state import validate_transition
from runnrr.exceptions import (
	IncompleteAcceptanceCriteria,
	TicketNotFoundError,
	ValidationError,
)
from runnrr.git.integration import GitIntegration


class TicketService:
	def __init__(self, root: Path):
		self.root = normalize_root(root)
		self._git = GitIntegration(self.root)

	def create(
		self,
		title: str,
		goal: str = "",
		type: TicketType = TicketType.FEATURE,
		priority: Priority = Priority.MEDIUM,
		epic: str | None = None,
		tags: list[str] | None = None,
		estimated_effort: int = 1,
		actor: str | None = None,
	) -> Ticket:
		init_runnrr(self.root)

		ticket_id = generate_id("ticket", self.root)
		now = datetime.now(timezone.utc)
		
		normalized_tags = [normalize_tag(t) for t in (tags or [])]
		
		ticket = Ticket(
			id=ticket_id,
			title=title,
			status=TicketStatus.BACKLOG,
			type=type,
			priority=priority,
			created_at=now,
			updated_at=now,
			epic=epic,
			tags=normalized_tags,
			estimated_effort=estimated_effort,
			goal_text=goal,
		)

		path = self.root / TICKET_DIRS[TicketStatus.BACKLOG.value] / f"{ticket_id}.md"
		ticket.path = path
		self._save(ticket)

		self._git.commit(f"runnrr: [{ticket_id}] created ({actor or 'system'})")
		return ticket

	def get(self, ticket_id: str) -> Ticket:
		path = find_ticket_path(ticket_id, self.root)
		if not path:
			raise TicketNotFoundError(f"Ticket '{ticket_id}' not found.")
		return parse_ticket(path)

	def list(
		self,
		status: str | None = None,
		owner: str | None = None,
		epic: str | None = None,
		tag: str | None = None,
	) -> list[Ticket]:
		statuses = [status] if status else list(TICKET_DIRS.keys())
		tickets: list[Ticket] = []

		for state in statuses:
			for path in list_tickets_in_state(state, self.root):
				tickets.append(parse_ticket(path))

		if owner:
			tickets = [t for t in tickets if t.owner == owner]
		if epic:
			tickets = [t for t in tickets if t.epic == epic]
		if tag:
			tag = normalize_tag(tag)
			tickets = [t for t in tickets if tag in t.tags]

		return tickets

	def transition(self, ticket_id: str, new_status: str, actor: str | None = None) -> Ticket:
		ticket = self.get(ticket_id)
		current_status = ticket.status.value

		validate_transition(current_status, new_status)

		if new_status == TicketStatus.DONE.value:
			unchecked = [i["text"] for i in ticket.acceptance_criteria if not i.get("done")]
			if unchecked:
				raise IncompleteAcceptanceCriteria(unchecked)

		if not ticket.path:
			raise TicketNotFoundError(f"Ticket '{ticket_id}' path missing.")

		new_path = move_ticket(ticket.path, new_status, self.root)
		ticket.status = TicketStatus(new_status)
		ticket.path = new_path
		self._save(ticket)

		self._git.commit(f"runnrr: [{ticket_id}] {current_status} → {new_status} ({actor or 'system'})")
		return ticket

	def update(self, ticket_id: str, updates: dict, actor: str | None = None) -> Ticket:
		ticket = self.get(ticket_id)
		for field, value in updates.items():
			if field == "tags" and isinstance(value, list):
				value = [normalize_tag(t) for t in value]
			if hasattr(ticket, field):
				setattr(ticket, field, value)
			else:
				raise ValidationError(f"Invalid field '{field}'")

		self._save(ticket)
		self._git.commit(f"runnrr: [{ticket_id}] updated ({actor or 'system'})")
		return ticket

	def log(self, ticket_id: str, message: str, actor: str | None = None) -> Ticket:
		ticket = self.get(ticket_id)
		entry = {
			"timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
			"message": message,
		}
		ticket.execution_log.append(entry)
		self._save(ticket)
		self._git.commit(f"runnrr: [{ticket_id}] log entry ({actor or 'system'})")
		return ticket

	def block(self, ticket_id: str, reason: str, actor: str | None = None) -> Ticket:
		ticket = self.transition(ticket_id, TicketStatus.BLOCKED.value, actor=actor)
		self.log(ticket_id, f"Blocked: {reason}", actor=actor)
		return ticket

	def get_next(self, tag: str | None = None, epic: str | None = None) -> Ticket | None:
		tickets = self.list(status=TicketStatus.TODO.value, tag=tag, epic=epic)
		if not tickets:
			return None

		done_tickets = {t.id for t in self.list(status=TicketStatus.DONE.value)}
		eligible = []
		for t in tickets:
			blocked = False
			for blocker_id in t.blocked_by:
				if blocker_id not in done_tickets:
					blocked = True
					break
			if not blocked:
				eligible.append(t)

		if not eligible:
			return None

		priority_order = {
			Priority.CRITICAL: 4,
			Priority.HIGH: 3,
			Priority.MEDIUM: 2,
			Priority.LOW: 1,
		}

		eligible.sort(key=lambda t: (
			-priority_order.get(t.priority, 0),
			t.estimated_effort,
			t.created_at
		))

		return eligible[0]

	def describe(self, ticket_id: str) -> dict:
		ticket = self.get(ticket_id)
		data = ticket.model_dump(mode="json")
		if ticket.path:
			data["path"] = str(ticket.path)
		return data

	def _save(self, ticket: Ticket) -> None:
		if not ticket.path:
			raise TicketNotFoundError("Ticket path missing.")
		content = serialize_ticket(ticket)
		import frontmatter
		post = frontmatter.loads(content)
		write_file(ticket.path, post.metadata, post.content)
