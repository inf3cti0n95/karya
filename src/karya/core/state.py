"""State machine for Karya."""

from typing import List
from karya.core.models import Ticket, TicketStatus

def validate_transition(current: str, target: str) -> None:
    """Validate a status transition."""
    valid_transitions = {
        "backlog": ["todo", "done"],
        "todo": ["in-progress", "backlog", "done"],
        "in-progress": ["done", "blocked", "todo"],
        "blocked": ["in-progress", "todo"],
        "done": ["in-progress", "todo"], # Allow reopening
    }
    
    if target not in valid_transitions.get(current, []):
        from karya.exceptions import InvalidTransitionError
        raise InvalidTransitionError(f"Cannot transition from {current} to {target}.")

def can_start(ticket: Ticket, blockers: List[Ticket]) -> bool:
    """Check if a ticket can be started."""
    if ticket.status != TicketStatus.TODO:
        return False
    
    for blocker in blockers:
        if blocker.status != TicketStatus.DONE:
            return False
    
    return True

def can_complete(ticket: Ticket) -> bool:
    """Check if a ticket can be completed."""
    if ticket.status != TicketStatus.IN_PROGRESS:
        return False
    
    for item in ticket.acceptance_criteria:
        if not item.get("done"):
            return False
            
    return True
