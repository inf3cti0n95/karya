"""ADR service operations."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import frontmatter

from karya.core.filesystem import (
	ADRS_DIR,
	append_event,
	find_adr_path,
	generate_adr_id,
	init_karya,
	normalize_root,
	write_adr_file,
)
from karya.core.models import ADR, ADRStatus, Event
from karya.core.parser import parse_adr, serialize_adr
from karya.exceptions import ADRFrozenError, ADRNotFoundError, UpdateForbiddenError
from karya.git.integration import GitIntegration
from karya.services.event_service import EventService
from karya.services.index_service import IndexService
from karya.services.epic_service import EpicService
from karya.services.ticket_service import TicketService

_FROZEN_FIELDS = {
	"context_text",
	"decision_text",
	"consequences_text",
	"alternatives_text",
}

_UPDATE_FIELDS = {
	"title",
	"deciders",
	"linked_tickets",
	"linked_epics",
	"tags",
	"context_text",
	"decision_text",
	"consequences_text",
	"alternatives_text",
}


class ADRService:
	def __init__(self, root: Path):
		self.root = normalize_root(root)
		self._tickets = TicketService(root)
		self._epics = EpicService(root)
		self._git = GitIntegration(root)
		self._index = IndexService(root)

	def create(
		self,
		title: str,
		context: str,
		decision: str,
		consequences: str = "",
		alternatives: str = "",
		deciders: list[str] | None = None,
		linked_tickets: list[str] | None = None,
		linked_epics: list[str] | None = None,
		tags: list[str] | None = None,
		actor: str | None = None,
	) -> ADR:
		init_karya(self.root)

		adr_id = generate_adr_id(self.root)
		adr = ADR(
			id=adr_id,
			title=title,
			status=ADRStatus.PROPOSED,
			date=date.today(),
			deciders=deciders or [],
			linked_tickets=linked_tickets or [],
			linked_epics=linked_epics or [],
			tags=tags or [],
			context_text=context,
			decision_text=decision,
			consequences_text=consequences,
			alternatives_text=alternatives,
		)

		path = self.root / ADRS_DIR / f"{adr_id}.md"
		adr.path = path
		self._write_adr(adr)

		append_event(
			Event(event="adr_created", data={"adr_id": adr_id}, actor=actor), self.root
		)
		self._git.commit(f"[{adr_id}] created ({actor or "system"})")

		# Bidirectional linking
		for ticket_id in adr.linked_tickets:
			self._link_ticket_one_way(adr_id, ticket_id)
		for epic_id in adr.linked_epics:
			self._link_epic_one_way(adr_id, epic_id)

		return adr

	def accept(self, adr_id: str, actor: str | None = None) -> ADR:
		adr = self.get(adr_id)
		adr.status = ADRStatus.ACCEPTED
		self._write_adr(adr)

		append_event(
			Event(event="adr_accepted", data={"adr_id": adr_id}, actor=actor), self.root
		)
		self._git.commit(f"[{adr_id}] accepted ({actor or "system"})")
		return adr

	def supersede(
		self,
		old_adr_id: str,
		new_title: str,
		context: str,
		decision: str,
		**kwargs,
	) -> ADR:
		actor = kwargs.get("actor")
		old_adr = self.get(old_adr_id)

		# Create new ADR
		new_adr = self.create(
			title=new_title, context=context, decision=decision, **kwargs
		)
		new_adr.supersedes = old_adr_id
		self._write_adr(new_adr)

		# Update old ADR
		old_adr.status = ADRStatus.SUPERSEDED
		old_adr.superseded_by = new_adr.id
		self._write_adr(old_adr)

		append_event(
			Event(
				event="adr_superseded",
				data={"old_id": old_adr_id, "new_id": new_adr.id},
				actor=actor,
			),
			self.root,
		)
		self._git.commit(
			f"[{old_adr_id}] superseded by {new_adr.id} ({actor or "system"})"
		)
		return new_adr

	def deprecate(self, adr_id: str, reason: str, actor: str | None = None) -> ADR:
		adr = self.get(adr_id)
		adr.status = ADRStatus.DEPRECATED
		self._write_adr(adr)

		append_event(
			Event(
				event="adr_deprecated",
				data={"adr_id": adr_id, "reason": reason},
				actor=actor,
			),
			self.root,
		)
		self._git.commit(f"[{adr_id}] deprecated ({actor or "system"})")
		return adr

	def get(self, adr_id: str) -> ADR:
		path = find_adr_path(adr_id, self.root)
		if not path:
			raise ADRNotFoundError(f"ADR '{adr_id}' not found.")
		return parse_adr(path)

	def list(
		self,
		status: ADRStatus | None = None,
		tag: str | None = None,
		linked_ticket: str | None = None,
		linked_epic: str | None = None,
	) -> list[ADR]:
		adrs: list[ADR] = []
		for path in (self.root / ADRS_DIR).glob("ADR-*.md"):
			adrs.append(self.get(path.stem))

		if status:
			adrs = [adr for adr in adrs if adr.status == status]
		if tag:
			adrs = [adr for adr in adrs if tag in adr.tags]
		if linked_ticket:
			adrs = [adr for adr in adrs if linked_ticket in adr.linked_tickets]
		if linked_epic:
			adrs = [adr for adr in adrs if linked_epic in adr.linked_epics]

		return adrs

	def update(self, adr_id: str, updates: dict, actor: str | None = None) -> ADR:
		adr = self.get(adr_id)

		is_accepted = adr.status == ADRStatus.ACCEPTED
		forbidden = [field for field in updates if field not in _UPDATE_FIELDS]
		if forbidden:
			raise UpdateForbiddenError(
				f"Updates not allowed for fields: {', '.join(forbidden)}"
			)

		if is_accepted:
			frozen_updates = [field for field in updates if field in _FROZEN_FIELDS]
			if frozen_updates:
				raise ADRFrozenError(adr_id, frozen_updates[0])

		for field, value in updates.items():
			setattr(adr, field, value)

		self._write_adr(adr)
		append_event(
			Event(
				event="adr_updated", data={"adr_id": adr_id, "updates": updates}, actor=actor
			),
			self.root,
		)
		self._git.commit(f"[{adr_id}] updated ({actor or "system"})")

		# Handle bidirectional links if they were updated
		if "linked_tickets" in updates:
			for ticket_id in updates["linked_tickets"]:
				self._link_ticket_one_way(adr_id, ticket_id)
		if "linked_epics" in updates:
			for epic_id in updates["linked_epics"]:
				self._link_epic_one_way(adr_id, epic_id)

		return adr

	def link_ticket(self, adr_id: str, ticket_id: str, actor: str | None = None) -> ADR:
		adr = self.get(adr_id)
		if ticket_id not in adr.linked_tickets:
			adr.linked_tickets.append(ticket_id)
		self._write_adr(adr)

		self._link_ticket_one_way(adr_id, ticket_id)

		append_event(
			Event(
				event="adr_ticket_linked",
				data={"adr_id": adr_id, "ticket_id": ticket_id},
				actor=actor,
			),
			self.root,
		)
		self._git.commit(f"[{adr_id}] linked ticket {ticket_id} ({actor or "system"})")
		return adr

	def link_epic(self, adr_id: str, epic_id: str, actor: str | None = None) -> ADR:
		adr = self.get(adr_id)
		if epic_id not in adr.linked_epics:
			adr.linked_epics.append(epic_id)
		self._write_adr(adr)

		self._link_epic_one_way(adr_id, epic_id)

		append_event(
			Event(
				event="adr_epic_linked",
				data={"adr_id": adr_id, "epic_id": epic_id},
				actor=actor,
			),
			self.root,
		)
		self._git.commit(f"[{adr_id}] linked epic {epic_id} ({actor or "system"})")
		return adr

	def describe(self, adr_id: str) -> dict:
		adr = self.get(adr_id)
		data = adr.model_dump(mode="json")
		if adr.path:
			data["path"] = str(adr.path)
		return data

	def _write_adr(self, adr: ADR) -> None:
		serialized = serialize_adr(adr)
		post = frontmatter.loads(serialized)
		if not adr.path:
			raise ADRNotFoundError(f"ADR {adr.id} path missing.")
		write_adr_file(adr.path, post.metadata, post.content)
		self._index.update_entity("adr", adr.id)

	def _link_ticket_one_way(self, adr_id: str, ticket_id: str) -> None:
		ticket = self._tickets.get(ticket_id)
		if adr_id not in ticket.linked_adrs:
			ticket.linked_adrs.append(adr_id)
			self._tickets._write_ticket(ticket)

	def _link_epic_one_way(self, adr_id: str, epic_id: str) -> None:
		epic = self._epics.get(epic_id)
		if adr_id not in epic.linked_adrs:
			epic.linked_adrs.append(adr_id)
			self._epics._write_epic(epic)
