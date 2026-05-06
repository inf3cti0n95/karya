"""Public Python SDK for Karya."""

from __future__ import annotations

from pathlib import Path

from karya.core.filesystem import KARYA_ROOT, init_karya
from karya.core.models import (
    ADR,
    Epic,
    Event,
    SearchResultItem,
    SearchResults,
    Sprint,
    Ticket,
)
from karya.services.adr_service import ADRService
from karya.services.context_service import ContextService
from karya.services.event_service import EventService
from karya.services.index_service import IndexService
from karya.services.link_service import LinkService
from karya.services.epic_service import EpicService
from karya.services.sprint_service import SprintService
from karya.services.ticket_service import TicketService


class KaryaClient:
    """Entry point for the Karya SDK."""

    def __init__(self, root: str | Path = ".", agent: str | None = None) -> None:
        root_path = Path(root)
        if root_path.name == KARYA_ROOT:
            root_path = root_path.parent

        self.root = root_path.resolve()
        self.agent = agent

        if not (self.root / KARYA_ROOT).exists():
            init_karya(self.root)

        self._tickets = TicketService(self.root)
        self._epics = EpicService(self.root)
        self._adrs = ADRService(self.root)
        self._sprints = SprintService(self.root)
        self._events = EventService(self.root)
        self._index = IndexService(self.root)
        self._links = LinkService(self.root)
        self._context = ContextService(self.root)

    def create_ticket(self, title: str, context: str = "", **kwargs) -> Ticket:
        return self._tickets.create(title=title, context=context, actor=self.agent, **kwargs)

    def get_next_ticket(self, agent: str | None = None) -> Ticket | None:
        return self._tickets.get_next(agent or self.agent or "")

    def list_tickets(self, status: str | None = None, agent: str | None = None) -> list[Ticket]:
        return self._tickets.list(status=status, agent=agent)

    def get_ticket(self, ticket_id: str) -> Ticket:
        return self._tickets.get(ticket_id)

    def describe_ticket(self, ticket_id: str) -> dict:
        return self._tickets.describe(ticket_id)

    def update_ticket(self, ticket_id: str, updates: dict) -> Ticket:
        return self._tickets.update(ticket_id, updates, actor=self.agent)

    def transition(self, ticket_id: str, status: str) -> Ticket:
        return self._tickets.transition(ticket_id, status, actor=self.agent)

    def log(self, ticket_id: str, message: str) -> Ticket:
        return self._tickets.log(ticket_id, message, actor=self.agent)

    def assign(self, ticket_id: str, agent: str) -> Ticket:
        return self._tickets.assign(ticket_id, agent, actor=self.agent)

    def block(self, ticket_id: str, reason: str) -> Ticket:
        return self._tickets.block(ticket_id, reason, actor=self.agent)

    def load_context(self) -> str:
        return self._context.load()

    def plan_sprint(self, limit: int = 5) -> Sprint:
        return self._sprints.plan(limit=limit)

    def create_epic(self, title: str, **kwargs) -> Epic:
        return self._epics.create(title=title, actor=self.agent, **kwargs)

    def get_epic(self, epic_id: str) -> Epic:
        return self._epics.get(epic_id)

    def list_epics(self, status: str | None = None, tag: str | None = None) -> list[Epic]:
        status_value = None
        if status:
            from karya.core.models import EpicStatus

            status_value = EpicStatus(status)
        return self._epics.list(status=status_value, tag=tag)

    def describe_epic(self, epic_id: str) -> dict:
        return self._epics.describe(epic_id)

    def update_epic(self, epic_id: str, updates: dict) -> Epic:
        return self._epics.update(epic_id, updates, actor=self.agent)

    def archive_epic(self, epic_id: str, reason: str) -> Epic:
        return self._epics.archive(epic_id, reason, actor=self.agent)

    def get_events(self, ticket_id: str | None = None, last: int = 20) -> list[Event]:
        return self._events.list(ticket_id=ticket_id, last=last)

    def create_adr(self, title: str, context: str, decision: str, **kwargs) -> ADR:
        return self._adrs.create(
            title=title, context=context, decision=decision, actor=self.agent, **kwargs
        )

    def get_adr(self, adr_id: str) -> ADR:
        return self._adrs.get(adr_id)

    def list_adrs(
        self, status: str | None = None, tag: str | None = None, **kwargs
    ) -> list[ADR]:
        status_value = None
        if status:
            from karya.core.models import ADRStatus

            status_value = ADRStatus(status)
        return self._adrs.list(status=status_value, tag=tag, **kwargs)

    def accept_adr(self, adr_id: str) -> ADR:
        return self._adrs.accept(adr_id, actor=self.agent)

    def supersede_adr(
        self, adr_id: str, new_title: str, context: str, decision: str, **kwargs
    ) -> ADR:
        return self._adrs.supersede(
            adr_id, new_title, context, decision, actor=self.agent, **kwargs
        )

    def deprecate_adr(self, adr_id: str, reason: str) -> ADR:
        return self._adrs.deprecate(adr_id, reason, actor=self.agent)

    def link_adr_ticket(self, adr_id: str, ticket_id: str) -> ADR:
        return self._adrs.link_ticket(adr_id, ticket_id, actor=self.agent)

    def link_adr_epic(self, adr_id: str, epic_id: str) -> ADR:
        return self._adrs.link_epic(adr_id, epic_id, actor=self.agent)

    def describe_adr(self, adr_id: str) -> dict:
        return self._adrs.describe(adr_id)

    def search(
        self,
        query: str,
        entity_type: str | None = None,
        tags: list[str] = [],
        status: str | None = None,
        since: date | None = None,
        limit: int = 10,
    ) -> SearchResults:
        return self._index.search(
            query=query,
            entity_type=entity_type,
            tags=tags,
            status=status,
            since=since,
            limit=limit,
        )

    def find_related(self, entity_id: str, limit: int = 5) -> SearchResults:
        return self._index.find_related(entity_id, limit=limit)

    def get_tags(self, entity_id: str | None = None) -> dict:
        return self._index.get_tags(entity_id)

    def rebuild_index(self) -> dict:
        return self._index.rebuild()

    def load_context_for_ticket(self, ticket_id: str) -> str:
        return self._context.load_for_ticket(ticket_id)

    def link(self, source_type: str, source_id: str, target_type: str, target_id: str) -> None:
        self._links.link(source_type, source_id, target_type, target_id, actor=self.agent)

    def get_links(self, entity_id: str) -> dict:
        return self._links.get_links(entity_id)

    def init(self) -> None:
        init_karya(self.root)
