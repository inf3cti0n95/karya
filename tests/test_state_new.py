"""Tests for edge cases and state machine."""

import pytest
from datetime import datetime, timezone
from runnrr.core.models import Ticket, TicketStatus
from runnrr.core.state import validate_transition, can_start, can_complete
from runnrr.exceptions import InvalidTransitionError

def test_validate_transitions():
    # Valid
    validate_transition("backlog", "todo")
    validate_transition("todo", "in-progress")
    validate_transition("in-progress", "done")
    validate_transition("blocked", "in-progress")
    validate_transition("done", "todo")
    
    # Invalid
    with pytest.raises(InvalidTransitionError):
        validate_transition("backlog", "in-progress")
    with pytest.raises(InvalidTransitionError):
        validate_transition("done", "blocked")

def test_can_start():
    now = datetime.now(timezone.utc)
    t = Ticket(id="T1", title="T", status=TicketStatus.TODO, created_at=now, updated_at=now)
    blocker = Ticket(id="B1", title="B", status=TicketStatus.DONE, created_at=now, updated_at=now)
    
    assert can_start(t, [blocker]) is True
    
    blocker.status = TicketStatus.IN_PROGRESS
    assert can_start(t, [blocker]) is False
    
    t.status = TicketStatus.BACKLOG
    assert can_start(t, []) is False

def test_can_complete():
    now = datetime.now(timezone.utc)
    t = Ticket(
        id="T1", title="T", status=TicketStatus.IN_PROGRESS, 
        created_at=now, updated_at=now,
        acceptance_criteria=[{"text": "AC1", "done": True}]
    )
    assert can_complete(t) is True
    
    t.acceptance_criteria[0]["done"] = False
    assert can_complete(t) is False
    
    t.status = TicketStatus.TODO
    assert can_complete(t) is False
