"""Context service for token-budgeted information retrieval using SQLite."""

from __future__ import annotations

from typing import Any, Dict, List
from runnrr.core.db import Database
from runnrr.services.ticket_service import TicketService
from runnrr.services.epic_service import EpicService
from runnrr.services.adr_service import ADRService

class ContextService:
    def __init__(self, db: Database):
        self.db = db
        self._tickets = TicketService(db)
        self._epics = EpicService(db)
        self._adrs = ADRService(db)

    def build_context(self, ticket_id: str, budget: int = 4000) -> Dict[str, Any]:
        """
        Build a token-budgeted context for a ticket.
        Includes ticket details, blockers, epic context, and relevant ADRs.
        """
        ticket = self._tickets.get(ticket_id)
        context = {
            "ticket": ticket.model_dump(mode="json"),
            "blockers": [],
            "epic": None,
            "adrs": [],
            "related_tickets": []
        }

        # 1. Get Blockers
        rows = self.db.execute(
            """
            SELECT t.* FROM tickets t
            JOIN dependencies d ON t.id = d.blocked_by
            WHERE d.ticket_id = ?
            """,
            (ticket_id,)
        ).fetchall()
        for row in rows:
            context["blockers"].append(dict(row))

        # 2. Get Epic Context
        if ticket.epic:
            try:
                epic = self._epics.get(ticket.epic)
                context["epic"] = epic.model_dump(mode="json")
            except Exception:
                pass

        # 3. Get Linked ADRs
        rows = self.db.execute(
            """
            SELECT a.* FROM adrs a
            JOIN links l ON a.id = l.target_id
            WHERE l.source_id = ? AND l.target_type = 'adr'
            """,
            (ticket_id,)
        ).fetchall()
        for row in rows:
            context["adrs"].append(dict(row))

        # 4. Get System Conventions (if any, for now we keep it simple)
        # In a real scenario, this would come from a system_settings table or similar
        context["conventions"] = "Standard development workflow. Log progress frequently."

        return context
