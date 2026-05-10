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
        
        sections = []
        tokens_used = 0
        excluded = []

        # Helper to "estimate" tokens (very rough for now)
        def estimate_tokens(obj: Any) -> int:
            return len(str(obj)) // 4

        # 1. Ticket Detail (Always first, usually fits)
        ticket_data = ticket.model_dump(mode="json")
        t_cost = estimate_tokens(ticket_data)
        sections.append({
            "id": ticket_id,
            "type": "ticket",
            "content": ticket_data,
            "tokens": t_cost
        })
        tokens_used += t_cost

        # 2. Get Blockers
        rows = self.db.execute(
            """
            SELECT t.* FROM tickets t
            JOIN dependencies d ON t.id = d.blocked_by
            WHERE d.ticket_id = ?
            """,
            (ticket_id,)
        ).fetchall()
        for row in rows:
            blocker_data = dict(row)
            # Fetch full ticket for detail if needed, but for now just the row
            cost = estimate_tokens(blocker_data)
            if tokens_used + cost <= budget:
                sections.append({
                    "id": blocker_data["id"],
                    "type": "blocker",
                    "content": blocker_data,
                    "tokens": cost
                })
                tokens_used += cost
            else:
                excluded.append({"id": blocker_data["id"], "type": "blocker"})

        # 3. Get Epic Context
        if ticket.epic:
            try:
                epic = self._epics.get(ticket.epic)
                epic_data = epic.model_dump(mode="json")
                cost = estimate_tokens(epic_data)
                if tokens_used + cost <= budget:
                    sections.append({
                        "id": ticket.epic,
                        "type": "epic",
                        "content": epic_data,
                        "tokens": cost
                    })
                    tokens_used += cost
                else:
                    excluded.append({"id": ticket.epic, "type": "epic"})
            except Exception:
                pass

        # 4. Get Linked ADRs
        rows = self.db.execute(
            """
            SELECT a.* FROM adrs a
            JOIN links l ON a.id = l.target_id
            WHERE l.source_id = ? AND l.target_type = 'adr'
            """,
            (ticket_id,)
        ).fetchall()
        for row in rows:
            adr_data = dict(row)
            cost = estimate_tokens(adr_data)
            if tokens_used + cost <= budget:
                sections.append({
                    "id": adr_data["id"],
                    "type": "direct_adr",
                    "content": adr_data,
                    "tokens": cost
                })
                tokens_used += cost
            else:
                excluded.append({"id": adr_data["id"], "type": "adr"})

        # 5. System Conventions
        convention = "Standard development workflow. Log progress frequently."
        cost = estimate_tokens(convention)
        if tokens_used + cost <= budget:
            sections.append({
                "id": "standard",
                "type": "convention",
                "content": convention,
                "tokens": cost
            })
            tokens_used += cost

        return {
            "ticket_id": ticket_id,
            "budget": budget,
            "tokens_used": tokens_used,
            "sections": sections,
            "excluded": excluded
        }
