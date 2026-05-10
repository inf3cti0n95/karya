"""Action service for computing valid transitions and the agent interface using SQLite."""

from __future__ import annotations

from typing import Dict, Any, List
from runnrr.core.db import Database
from runnrr.core.models import Ticket, TicketStatus
from runnrr.services.ticket_service import TicketService
from runnrr.services.context_service import ContextService

class ActionService:
    def __init__(self, db: Database):
        self.db = db
        self._tickets = TicketService(db)
        self._context = ContextService(db)

    def valid_actions(self, ticket_id: str) -> List[Dict[str, Any]]:
        """Compute valid transitions and commands for a ticket."""
        ticket = self._tickets.get(ticket_id)
        current = ticket.status.value
        
        # Define valid transitions (matching core.state logic)
        transitions = {
            "backlog": ["todo"],
            "todo": ["backlog", "in-progress", "blocked"],
            "in-progress": ["todo", "blocked", "done"],
            "blocked": ["todo"],
            "done": ["in-progress"] # allow reopening
        }
        
        allowed = transitions.get(current, [])
        actions = []
        
        for target in allowed:
            cmd = f"runnrr start {ticket_id}" if target == "in-progress" else \
                  f"runnrr done {ticket_id}" if target == "done" else \
                  f"runnrr block {ticket_id} <reason>" if target == "blocked" else \
                  f"runnrr transition {ticket_id} {target}" # generic fallback
            
            actions.append({
                "action": target,
                "available": True,
                "command": cmd
            })
            
        return actions

    def exec(self, ticket_id: str | None = None) -> Dict[str, Any]:
        """
        Agent Executive Interface.
        If no ticket_id, pick the highest priority 'todo' ticket.
        """
        if not ticket_id:
            ticket = self._tickets.get_next()
            if not ticket:
                raise Exception("No actionable tickets found.")
            ticket_id = ticket.id
        else:
            ticket = self._tickets.get(ticket_id)

        context_data = self._context.build_context(ticket_id)
        actions = self.valid_actions(ticket_id)
        
        # Suggest command
        suggested_command = None
        for a in actions:
            if a["action"] == "in-progress":
                suggested_command = a["command"]
                break

        return {
            "ticket": ticket.model_dump(mode="json"),
            "context": context_data,
            "valid_actions": actions,
            "suggested_command": suggested_command
        }
