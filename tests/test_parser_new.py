"""Unit tests for the new Phase A parser."""

from datetime import datetime, date, timezone
from pathlib import Path
import pytest
from karya.core.models import Ticket, TicketStatus, TicketType, Priority, Epic, ADR, ADRStatus
from karya.core.parser import parse_ticket, serialize_ticket, parse_epic, serialize_epic, parse_adr, serialize_adr

def test_ticket_roundtrip(tmp_path):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    ticket = Ticket(
        id="TICKET-001",
        title="Test Ticket",
        status=TicketStatus.TODO,
        type=TicketType.FEATURE,
        priority=Priority.MEDIUM,
        created_at=now,
        updated_at=now,
        goal_text="Our Goal",
        tasks=[{"text": "T1", "done": True}, {"text": "T2", "done": False}],
        acceptance_criteria=[{"text": "AC1", "done": False}],
        execution_log=[{"timestamp": "2026-05-08T12:00:00Z", "message": "Log 1"}],
        notes_text="Some notes here"
    )
    
    path = tmp_path / "TICKET-001.md"
    content = serialize_ticket(ticket)
    path.write_text(content, encoding="utf-8")
    
    parsed = parse_ticket(path)
    
    assert parsed.id == ticket.id
    assert parsed.title == ticket.title
    assert parsed.status == ticket.status
    assert parsed.goal_text == "Our Goal"
    assert len(parsed.tasks) == 2
    assert parsed.tasks[0]["done"] is True
    assert parsed.execution_log[0]["message"] == "Log 1"
    assert parsed.notes_text == "Some notes here"

def test_epic_roundtrip(tmp_path):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    epic = Epic(
        id="EPIC-001",
        title="Test Epic",
        created_at=now,
        updated_at=now,
        goal_text="Epic Goal",
        success_metrics=["Metric 1", "Metric 2"],
        notes_text="Epic notes"
    )
    
    path = tmp_path / "EPIC-001.md"
    content = serialize_epic(epic)
    path.write_text(content, encoding="utf-8")
    
    parsed = parse_epic(path)
    assert parsed.id == "EPIC-001"
    assert parsed.goal_text == "Epic Goal"
    assert parsed.success_metrics == ["Metric 1", "Metric 2"]

def test_adr_roundtrip(tmp_path):
    adr = ADR(
        id="ADR-001",
        title="Test ADR",
        status=ADRStatus.PROPOSED,
        date=date(2026, 5, 8),
        context_text="Context",
        decision_text="Decision",
        consequences_text="Consequences",
        alternatives_text="Alternatives"
    )
    
    path = tmp_path / "ADR-001.md"
    content = serialize_adr(adr)
    path.write_text(content, encoding="utf-8")
    
    parsed = parse_adr(path)
    assert parsed.id == "ADR-001"
    assert parsed.status == ADRStatus.PROPOSED
    assert parsed.decision_text == "Decision"
