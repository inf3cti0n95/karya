"""Parser tests."""

from datetime import datetime, timezone
from pathlib import Path

from karya.core.models import Priority, Ticket, TicketStatus, TicketType
from karya.core.parser import parse_ticket, serialize_ticket


def _write_ticket(path: Path) -> None:
    content = """---
id: TICKET-001
title: Test ticket
status: todo
type: feature
priority: medium
created_at: 2026-05-04T10:00:00Z
updated_at: 2026-05-04T10:00:00Z
---
## Context

Some context.

## Goal

Goal text.

## Scope

Scope text.

## 🪜 Tasks

- [ ] First task
- [x] Done task

## 🧪 Acceptance Criteria

- [x] Ship it

## 📜 Execution Log

<!-- [{"timestamp":"2026-05-04T10:00:00Z","message":"Started"}] -->

## 🧭 Agent Instructions

Follow the plan.
"""
    path.write_text(content, encoding="utf-8")


def test_parse_ticket(tmp_path: Path) -> None:
    path = tmp_path / "TICKET-001.md"
    _write_ticket(path)

    ticket = parse_ticket(path)

    assert ticket.id == "TICKET-001"
    assert ticket.context_text == "Some context."
    assert ticket.tasks[0]["done"] is False
    assert ticket.tasks[1]["done"] is True
    assert ticket.acceptance_criteria[0]["done"] is True
    assert ticket.execution_log[0]["message"] == "Started"
    assert ticket.agent_instructions == "Follow the plan."


def test_serialize_ticket_round_trip(tmp_path: Path) -> None:
    ticket = Ticket(
        id="TICKET-002",
        title="Round trip",
        status=TicketStatus.TODO,
        type=TicketType.FEATURE,
        priority=Priority.MEDIUM,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        tasks=[{"text": "One", "done": False}],
        acceptance_criteria=[{"text": "Two", "done": True}],
        execution_log=[{"timestamp": "2026-05-04T10:00:00Z", "message": "Log"}],
    )

    serialized = serialize_ticket(ticket)
    path = tmp_path / "TICKET-002.md"
    path.write_text(serialized, encoding="utf-8")

    parsed = parse_ticket(path)

    assert parsed.id == "TICKET-002"
    assert parsed.tasks[0]["text"] == "One"
    assert parsed.acceptance_criteria[0]["done"] is True


def test_parse_missing_optional_sections(tmp_path: Path) -> None:
    content = """---
id: TICKET-003
title: Missing sections
status: backlog
type: chore
priority: low
created_at: 2026-05-04T10:00:00Z
updated_at: 2026-05-04T10:00:00Z
---
"""
    path = tmp_path / "TICKET-003.md"
    path.write_text(content, encoding="utf-8")

    ticket = parse_ticket(path)
    assert ticket.context_text is None
    assert ticket.tasks == []
    assert ticket.execution_log == []
