"""Link service for managing bidirectional relationships."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from karya.core.filesystem import normalize_root, append_event
from karya.core.models import Event
from karya.exceptions import InvalidLinkError, TicketNotFoundError, EpicNotFoundError, ADRNotFoundError
from karya.services.adr_service import ADRService
from karya.services.epic_service import EpicService
from karya.services.ticket_service import TicketService


class LinkService:
	"""
	Manages bidirectional links between entities.
	The single source of truth for cross-entity relationships.
	"""
	def __init__(self, root: Path):
		self.root = normalize_root(root)
		self._ticket_service: TicketService | None = None
		self._adr_service: ADRService | None = None
		self._epic_service: EpicService | None = None

	@property
	def _tickets(self) -> TicketService:
		if not self._ticket_service:
			self._ticket_service = TicketService(self.root)
		return self._ticket_service

	@property
	def _adrs(self) -> ADRService:
		if not self._adr_service:
			self._adr_service = ADRService(self.root)
		return self._adr_service

	@property
	def _epics(self) -> EpicService:
		if not self._epic_service:
			self._epic_service = EpicService(self.root)
		return self._epic_service

	def link(self, source_type: str, source_id: str, target_type: str, target_id: str, actor: str | None = None) -> None:
		"""
		Route to correct service method based on entity types.
		"""
		# Normalize types
		st = source_type.lower()
		tt = target_type.lower()

		if st == "ticket" and tt == "epic":
			self._epics.link_ticket(target_id, source_id, actor=actor)
		elif st == "epic" and tt == "ticket":
			self._epics.link_ticket(source_id, target_id, actor=actor)
		elif st == "ticket" and tt == "adr":
			self._adrs.link_ticket(target_id, source_id, actor=actor)
		elif st == "adr" and tt == "ticket":
			self._adrs.link_ticket(source_id, target_id, actor=actor)
		elif st == "epic" and tt == "adr":
			self._adrs.link_epic(target_id, source_id, actor=actor)
		elif st == "adr" and tt == "epic":
			self._adrs.link_epic(source_id, target_id, actor=actor)
		else:
			raise InvalidLinkError(f"Linking {st} and {tt} is not supported.")

		append_event(
			Event(
				event="link_created",
				data={
					"source_type": st,
					"source_id": source_id,
					"target_type": tt,
					"target_id": target_id
				},
				actor=actor
			),
			self.root
		)

	def unlink(self, source_type: str, source_id: str, target_type: str, target_id: str, actor: str | None = None) -> None:
		st = source_type.lower()
		tt = target_type.lower()

		if st == "ticket" and tt == "epic":
			self._epics.unlink_ticket(target_id, source_id, actor=actor)
		elif st == "epic" and tt == "ticket":
			self._epics.unlink_ticket(source_id, target_id, actor=actor)
		# Unlinking for ADRs is not explicitly in the prompt methods, but we can implement if needed.
		# For now, stick to prompt's listed methods in services.
		else:
			raise InvalidLinkError(f"Unlinking {st} and {tt} is not supported yet.")

		append_event(
			Event(
				event="link_removed",
				data={
					"source_type": st,
					"source_id": source_id,
					"target_type": tt,
					"target_id": target_id
				},
				actor=actor
			),
			self.root
		)

	def get_links(self, entity_id: str) -> dict:
		"""Show all links for an entity."""
		# We need to determine entity type from ID
		if entity_id.startswith("TICKET-"):
			return self._get_ticket_links(entity_id)
		elif entity_id.startswith("EPIC-"):
			return self._get_epic_links(entity_id)
		elif entity_id.startswith("ADR-"):
			return self._get_adr_links(entity_id)
		else:
			raise ValueError(f"Unknown entity ID format: {entity_id}")

	def _get_ticket_links(self, ticket_id: str) -> dict:
		ticket = self._tickets.get(ticket_id)
		links = {
			"epic": [],
			"adrs": [],
			"blocked_by": ticket.blocked_by,
			"dependencies": ticket.dependencies
		}
		if ticket.epic:
			try:
				epic = self._epics.get(ticket.epic)
				links["epic"].append({"id": epic.id, "title": epic.title, "status": epic.status.value if epic.status else "planned"})
			except Exception:
				pass
		
		for adr_id in ticket.linked_adrs:
			try:
				adr = self._adrs.get(adr_id)
				links["adrs"].append({"id": adr.id, "title": adr.title, "status": adr.status.value})
			except Exception:
				pass
		
		return links

	def _get_epic_links(self, epic_id: str) -> dict:
		epic = self._epics.get(epic_id)
		links = {
			"parent_epic": epic.parent_epic,
			"child_epics": epic.child_epics,
			"tickets": [],
			"adrs": []
		}
		for tid in epic.tickets:
			try:
				t = self._tickets.get(tid)
				links["tickets"].append({"id": t.id, "title": t.title, "status": t.status.value})
			except Exception:
				pass
		
		for aid in epic.linked_adrs:
			try:
				a = self._adrs.get(aid)
				links["adrs"].append({"id": a.id, "title": a.title, "status": a.status.value})
			except Exception:
				pass
		
		return links

	def _get_adr_links(self, adr_id: str) -> dict:
		adr = self._adrs.get(adr_id)
		links = {
			"tickets": [],
			"epics": [],
			"supersedes": adr.supersedes,
			"superseded_by": adr.superseded_by
		}
		for tid in adr.linked_tickets:
			try:
				t = self._tickets.get(tid)
				links["tickets"].append({"id": t.id, "title": t.title, "status": t.status.value})
			except Exception:
				pass
		
		for eid in adr.linked_epics:
			try:
				e = self._epics.get(eid)
				links["epics"].append({"id": e.id, "title": e.title, "status": e.status.value if e.status else "planned"})
			except Exception:
				pass
		
		return links
