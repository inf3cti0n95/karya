"""Ticket service tests."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from runnrr.core.models import Priority, TicketStatus
from runnrr.exceptions import IncompleteAcceptanceCriteria, InvalidTransitionError
from runnrr.services.ticket_service import TicketService


def test_create_and_get(runnrr_root: Path) -> None:
    service = TicketService(runnrr_root)
    ticket = service.create("Title")

    assert ticket.status == TicketStatus.BACKLOG
    loaded = service.get(ticket.id)
    assert loaded.id == ticket.id


def test_transition_moves_ticket(runnrr_root: Path) -> None:
    service = TicketService(runnrr_root)
    ticket = service.create("Transition")
    service.transition(ticket.id, "todo")

    updated = service.get(ticket.id)
    assert updated.status == TicketStatus.TODO


def test_transition_done_requires_acceptance(runnrr_root: Path) -> None:
    service = TicketService(runnrr_root)
    ticket = service.create("Needs AC")
    service.transition(ticket.id, "todo")
    service.transition(ticket.id, "in-progress")

    ticket = service.get(ticket.id)
    ticket.acceptance_criteria = [{"text": "AC", "done": False}]
    service._save(ticket)

    with pytest.raises(IncompleteAcceptanceCriteria):
        service.transition(ticket.id, "done")


def test_transition_invalid(runnrr_root: Path) -> None:
    service = TicketService(runnrr_root)
    ticket = service.create("Invalid")
    # backlog -> in-progress is invalid
    with pytest.raises(InvalidTransitionError):
        service.transition(ticket.id, "in-progress")


def test_log_appends_execution_entry(runnrr_root: Path) -> None:
    service = TicketService(runnrr_root)
    ticket = service.create("Log")
    service.log(ticket.id, "First")
    updated = service.get(ticket.id)
    assert updated.execution_log[-1]["message"] == "First"


def test_get_next_respects_priority_and_dependencies(runnrr_root: Path) -> None:
    service = TicketService(runnrr_root)
    first = service.create("First", priority=Priority.LOW)
    second = service.create("Second", priority=Priority.HIGH)

    service.transition(first.id, "todo")
    service.transition(second.id, "todo")

    # Pass no tag to get any eligible ticket
    next_ticket = service.get_next()
    assert next_ticket is not None
    assert next_ticket.id == second.id

    blocker = service.create("Blocker")
    service.transition(blocker.id, "todo")
    service.transition(blocker.id, "in-progress")
    
    dependent = service.create("Dependent")
    service.update(dependent.id, {"blocked_by": [blocker.id]})
    service.transition(dependent.id, "todo")

    # Dependent is blocked by in-progress Blocker
    next_ticket = service.get_next()
    assert next_ticket is not None
    assert next_ticket.id != dependent.id
