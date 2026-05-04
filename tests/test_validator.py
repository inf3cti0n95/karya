"""Validator tests."""

from datetime import datetime, timezone

from karya.core.models import Priority, Ticket, TicketStatus, TicketType
from karya.core.validator import validate_completable, validate_ticket


def _ticket(**overrides: object) -> Ticket:
    data = {
        "id": "TICKET-001",
        "title": "Valid",
        "status": TicketStatus.TODO,
        "type": TicketType.FEATURE,
        "priority": Priority.MEDIUM,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return Ticket(**data)


def test_validate_ticket_valid() -> None:
    ticket = _ticket()
    assert validate_ticket(ticket) == []


def test_validate_ticket_invalid_id() -> None:
    ticket = _ticket(id="BAD-1")
    assert any("Ticket id" in error for error in validate_ticket(ticket))


def test_validate_ticket_empty_title() -> None:
    ticket = _ticket(title=" ")
    assert any("title" in error.lower() for error in validate_ticket(ticket))


def test_validate_ticket_effort_range() -> None:
    ticket = _ticket().model_copy(update={"estimated_effort": 7})
    assert any("effort" in error.lower() for error in validate_ticket(ticket))


def test_validate_ticket_self_dependency() -> None:
    ticket = _ticket(dependencies=["TICKET-001"])
    assert any("depend" in error.lower() for error in validate_ticket(ticket))


def test_validate_ticket_agents_allowed_empty() -> None:
    ticket = _ticket(agents_allowed=["", "agent"])
    assert any("agents_allowed" in error for error in validate_ticket(ticket))


def test_validate_completable_unchecked() -> None:
    ticket = _ticket(
        acceptance_criteria=[
            {"text": "Done", "done": True},
            {"text": "Todo", "done": False},
        ]
    )

    assert validate_completable(ticket) == ["Todo"]
