"""Runnrr SDK Client."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from runnrr.core.filesystem import init_runnrr, normalize_root
from runnrr.core.models import ADR, Epic, Priority, Ticket, TicketStatus, TicketType, EpicType
from runnrr.services.adr_service import ADRService
from runnrr.services.epic_service import EpicService
from runnrr.services.ticket_service import TicketService
from runnrr.services.context_service import ContextService
from runnrr.services.search_service import SearchService
from runnrr.services.link_service import LinkService
from runnrr.services.action_service import ActionService


class RunnrrClient:
	def __init__(self, root: str | Path = ".", agent: str | None = None):
		self.root = normalize_root(Path(root))
		self.agent = agent
		self._tickets = TicketService(self.root)
		self._epics = EpicService(self.root)
		self._adrs = ADRService(self.root)
		self._context = ContextService(self.root)
		self._search = SearchService(self.root)
		self._links = LinkService(self.root)
		self._actions = ActionService(self.root)

	def init(self) -> None:
		init_runnrr(self.root)

	# Tickets
	def get_next_ticket(self, tag: str | None = None, epic: str | None = None) -> Ticket | None:
		return self._tickets.get_next(tag=tag, epic=epic)

	def build_context(self, ticket_id: str, budget: int = 4000) -> Dict[str, Any]:
		return self._context.build_context(ticket_id, budget=budget)
		
	# Actions (Agent Interface)
	def valid_actions(self, ticket_id: str) -> List[Dict[str, Any]]:
		return self._actions.valid_actions(ticket_id)
		
	def execute(self, ticket_id: str | None = None) -> Dict[str, Any]:
		return self._actions.exec(ticket_id)

	# Search & Links
	def rebuild_index(self) -> None:
		self._search.rebuild_index()
		
	def search(self, query: str) -> List[Dict[str, Any]]:
		return self._search.search(query)
		
	def find_related(self, entity_id: str) -> List[Dict[str, Any]]:
		return self._search.find_related(entity_id)
		
	def link(self, source_id: str, target_id: str) -> None:
		self._links.link(source_id, target_id, actor=self.agent)

	def create_ticket(
		self,
		title: str,
		goal: str = "",
		type: TicketType = TicketType.FEATURE,
		priority: Priority = Priority.MEDIUM,
		epic: str | None = None,
		tags: list[str] | None = None,
		estimated_effort: int = 1,
	) -> Ticket:
		return self._tickets.create(
			title=title,
			goal=goal,
			type=type,
			priority=priority,
			epic=epic,
			tags=tags,
			estimated_effort=estimated_effort,
			actor=self.agent,
		)

	def get_ticket(self, ticket_id: str) -> Ticket:
		return self._tickets.get(ticket_id)

	def list_tickets(
		self,
		status: str | None = None,
		owner: str | None = None,
		epic: str | None = None,
		tag: str | None = None,
	) -> list[Ticket]:
		return self._tickets.list(status=status, owner=owner, epic=epic, tag=tag)

	def transition(self, ticket_id: str, new_status: str) -> Ticket:
		return self._tickets.transition(ticket_id, new_status, actor=self.agent)

	def update_ticket(self, ticket_id: str, updates: dict) -> Ticket:
		return self._tickets.update(ticket_id, updates, actor=self.agent)

	def log(self, ticket_id: str, message: str) -> Ticket:
		return self._tickets.log(ticket_id, message, actor=self.agent)

	def block(self, ticket_id: str, reason: str) -> Ticket:
		return self._tickets.block(ticket_id, reason, actor=self.agent)

	def describe_ticket(self, ticket_id: str) -> dict:
		return self._tickets.describe(ticket_id)

	# Epics
	def create_epic(
		self,
		title: str,
		goal: str = "",
		type: EpicType = EpicType.FEATURE,
		priority: Priority = Priority.MEDIUM,
		tags: list[str] | None = None,
	) -> Epic:
		return self._epics.create(
			title=title,
			goal=goal,
			type=type,
			priority=priority,
			tags=tags,
			actor=self.agent,
		)

	def get_epic(self, epic_id: str) -> Epic:
		return self._epics.get(epic_id)

	def list_epics(self, tag: str | None = None) -> list[Epic]:
		return self._epics.list(tag=tag)

	def describe_epic(self, epic_id: str) -> dict:
		return self._epics.describe(epic_id)

	# ADRs
	def create_adr(
		self,
		title: str,
		context: str,
		decision: str,
		consequences: str = "",
		alternatives: str = "",
		linked_tickets: list[str] | None = None,
		linked_epics: list[str] | None = None,
		tags: list[str] | None = None,
	) -> ADR:
		return self._adrs.create(
			title=title,
			context=context,
			decision=decision,
			consequences=consequences,
			alternatives=alternatives,
			linked_tickets=linked_tickets,
			linked_epics=linked_epics,
			tags=tags,
			actor=self.agent,
		)

	def get_adr(self, adr_id: str) -> ADR:
		return self._adrs.get(adr_id)

	def list_adrs(self, status: str | None = None, tag: str | None = None) -> list[ADR]:
		return self._adrs.list(status=status, tag=tag)

	def accept_adr(self, adr_id: str) -> ADR:
		return self._adrs.accept(adr_id, actor=self.agent)

	def describe_adr(self, adr_id: str) -> dict:
		return self._adrs.describe(adr_id)
