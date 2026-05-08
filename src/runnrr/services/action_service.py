"""Action service for computing valid transitions and the agent interface."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List

from runnrr.core.filesystem import normalize_root
from runnrr.services.ticket_service import TicketService
from runnrr.services.context_service import ContextService
from runnrr.core.models import TicketStatus

class ActionService:
    def __init__(self, root: Path):
        self.root = normalize_root(root)
        self._tickets = TicketService(self.root)
        self._context = ContextService(self.root)

    def valid_actions(self, ticket_id: str) -> List[Dict[str, Any]]:
        ticket = self._tickets.get(ticket_id)
        status = ticket.status
        
        actions = []
        
        # start_ticket
        start_action = {
            "action": "start_ticket",
            "command": f"runnrr start {ticket_id}",
            "reason": "Move ticket into progress."
        }
        if status == TicketStatus.TODO:
            done_tickets = {t.id for t in self._tickets.list(status=TicketStatus.DONE.value)}
            blocked_by = []
            for b_id in ticket.blocked_by:
                if b_id not in done_tickets:
                    blocked_by.append(f"{b_id} is not done")
            if blocked_by:
                start_action["available"] = False
                start_action["blocked_by"] = blocked_by
            else:
                start_action["available"] = True
        else:
            start_action["available"] = False
            start_action["reason"] = f"Ticket is {status.value}, not todo"
        actions.append(start_action)

        # done_ticket
        done_action = {
            "action": "done_ticket",
            "command": f"runnrr done {ticket_id}",
            "reason": "Complete the ticket."
        }
        if status == TicketStatus.IN_PROGRESS:
            unchecked = [ac["text"] for ac in ticket.acceptance_criteria if not ac.get("done")]
            if unchecked:
                done_action["available"] = False
                done_action["blocked_by"] = [f"Acceptance criteria '{text}' is unchecked" for text in unchecked]
            else:
                done_action["available"] = True
        else:
            done_action["available"] = False
            done_action["reason"] = f"Ticket is {status.value}, not in-progress"
        actions.append(done_action)

        # block_ticket
        block_action = {
            "action": "block_ticket",
            "command": f"runnrr block {ticket_id} \"<reason>\"",
            "reason": "Block the ticket on a dependency."
        }
        if status == TicketStatus.IN_PROGRESS:
            block_action["available"] = True
        else:
            block_action["available"] = False
            block_action["reason"] = f"Ticket is {status.value}, not in-progress"
        actions.append(block_action)

        # log_ticket
        log_action = {
            "action": "log_ticket",
            "command": f"runnrr log {ticket_id} \"<message>\"",
            "reason": "Log progress on the ticket."
        }
        if status in (TicketStatus.IN_PROGRESS, TicketStatus.BLOCKED):
            log_action["available"] = True
        else:
            log_action["available"] = False
            log_action["reason"] = f"Ticket is {status.value}, not active"
        actions.append(log_action)

        # create_ticket
        actions.append({
            "action": "create_ticket",
            "command": "runnrr create \"<title>\"",
            "reason": "Create related work.",
            "available": True
        })

        return actions

    def exec(self, ticket_id: str | None = None) -> Dict[str, Any]:
        if not ticket_id:
            ticket = self._tickets.get_next()
            if not ticket:
                raise Exception("No executable tickets found.")
            ticket_id = ticket.id
        else:
            ticket = self._tickets.get(ticket_id)
            
        context_data = self._context.build_context(ticket_id)
        actions = self.valid_actions(ticket_id)
        
        suggested_command = "runnrr log"
        for a in actions:
            if a["action"] == "start_ticket" and a.get("available"):
                suggested_command = f"runnrr start {ticket_id}"
                break
            if a["action"] == "done_ticket" and a.get("available"):
                suggested_command = f"runnrr done {ticket_id}"
                break

        return {
            "ticket": ticket.model_dump(mode="json"),
            "context": context_data,
            "valid_actions": actions,
            "suggested_command": suggested_command
        }
