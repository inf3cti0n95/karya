"""Unit tests for the new Phase A models."""

from datetime import datetime, date, timezone
import pytest
from pydantic import ValidationError
from runnrr.core.models import Ticket, TicketStatus, TicketType, Priority, Epic, EpicType, ADR, ADRStatus

def test_ticket_model_minimal():
    now = datetime.now(timezone.utc)
    ticket = Ticket(
        id="TICKET-001",
        title="Test Ticket",
        status=TicketStatus.BACKLOG,
        created_at=now,
        updated_at=now
    )
    assert ticket.id == "TICKET-001"
    assert ticket.status == TicketStatus.BACKLOG
    assert ticket.type == TicketType.FEATURE
    assert ticket.priority == Priority.MEDIUM

def test_ticket_model_full():
    now = datetime.now(timezone.utc)
    ticket = Ticket(
        id="TICKET-001",
        title="Test Ticket",
        status=TicketStatus.IN_PROGRESS,
        type=TicketType.BUG,
        priority=Priority.CRITICAL,
        created_at=now,
        updated_at=now,
        owner="agent-1",
        epic="EPIC-001",
        tags=["auth", "api"],
        dependencies=["TICKET-000"],
        blocked_by=["TICKET-002"],
        estimated_effort=3,
        linked_adrs=["ADR-001"],
        goal_text="The goal",
        tasks=[{"text": "Task 1", "done": False}],
        acceptance_criteria=[{"text": "AC 1", "done": True}],
        execution_log=[{"timestamp": "2026-05-08T12:00:00Z", "message": "Started"}],
        notes_text="Some notes"
    )
    assert ticket.owner == "agent-1"
    assert ticket.estimated_effort == 3
    assert len(ticket.tags) == 2

def test_epic_model():
    now = datetime.now(timezone.utc)
    epic = Epic(
        id="EPIC-001",
        title="Main Epic",
        type=EpicType.INITIATIVE,
        priority=Priority.HIGH,
        created_at=now,
        updated_at=now,
        tags=["big-feature"],
        goal_text="Finish the feature",
        success_metrics=["Metric 1"],
        notes_text="Epic notes"
    )
    assert epic.id == "EPIC-001"
    assert epic.type == EpicType.INITIATIVE

def test_adr_model():
    adr = ADR(
        id="ADR-001",
        title="Use SQLite",
        status=ADRStatus.ACCEPTED,
        date=date(2026, 5, 8),
        linked_tickets=["TICKET-001"],
        tags=["db"],
        context_text="Context",
        decision_text="Decision",
        consequences_text="Consequences",
        alternatives_text="Alternatives"
    )
    assert adr.id == "ADR-001"
    assert adr.status == ADRStatus.ACCEPTED
