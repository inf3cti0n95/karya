"""Public Python SDK for Karya."""

from __future__ import annotations

from pathlib import Path

from karya.core.filesystem import KARYA_ROOT, init_karya
from karya.core.models import Event, Sprint, Ticket
from karya.services.context_service import ContextService
from karya.services.event_service import EventService
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
        self._sprints = SprintService(self.root)
        self._events = EventService(self.root)
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

    def get_events(self, ticket_id: str | None = None, last: int = 20) -> list[Event]:
        return self._events.list(ticket_id=ticket_id, last=last)

    def init(self) -> None:
        init_karya(self.root)
