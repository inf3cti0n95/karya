"""Ticket service tests using SQLite."""

from datetime import datetime, timezone
from pathlib import Path
import pytest
from runnrr.core.models import Priority, TicketStatus
from runnrr.core.db import Database
from runnrr.exceptions import IncompleteAcceptanceCriteria, InvalidTransitionError
from runnrr.services.ticket_service import TicketService


def test_create_and_get(db: Database) -> None:
    service = TicketService(db)
    ticket = service.create("Title")

    assert ticket.status == TicketStatus.BACKLOG
    loaded = service.get(ticket.id)
    assert loaded.id == ticket.id


def test_transition_moves_ticket(db: Database) -> None:
    service = TicketService(db)
    ticket = service.create("Transition")
    service.transition(ticket.id, "todo")

    updated = service.get(ticket.id)
    assert updated.status == TicketStatus.TODO


def test_transition_done_requires_acceptance(db: Database) -> None:
    service = TicketService(db)
    ticket = service.create("Needs AC")
    service.transition(ticket.id, "todo")
    service.transition(ticket.id, "in-progress")

    # Manually insert an incomplete AC
    db.execute(
        "INSERT INTO acceptance_criteria (ticket_id, text, done) VALUES (?, ?, ?)",
        (ticket.id, "AC", 0)
    )

    with pytest.raises(IncompleteAcceptanceCriteria):
        service.transition(ticket.id, "done")


def test_transition_invalid(db: Database) -> None:
    service = TicketService(db)
    ticket = service.create("Invalid")
    # backlog -> in-progress is invalid
    with pytest.raises(InvalidTransitionError):
        service.transition(ticket.id, "in-progress")


def test_log_appends_execution_entry(db: Database) -> None:
    service = TicketService(db)
    ticket = service.create("Log")
    service.log(ticket.id, "First")
    updated = service.get(ticket.id)
    assert updated.execution_log[-1]["message"] == "First"


def test_get_next_respects_priority_and_dependencies(db: Database) -> None:
    service = TicketService(db)
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
    # Manually add dependency
    db.execute("INSERT INTO dependencies (ticket_id, blocked_by) VALUES (?, ?)", (dependent.id, blocker.id))
    service.transition(dependent.id, "todo")

    # Dependent is blocked by in-progress Blocker
    next_ticket = service.get_next()
    assert next_ticket is not None
    assert next_ticket.id != dependent.id
