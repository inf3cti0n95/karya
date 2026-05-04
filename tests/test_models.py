"""Model tests."""

from datetime import datetime, timezone

from karya.core.models import Priority, Ticket, TicketStatus, TicketType


def test_ticket_is_completable() -> None:
    ticket = Ticket(
        id="TICKET-001",
        title="Example",
        status=TicketStatus.TODO,
        type=TicketType.FEATURE,
        priority=Priority.MEDIUM,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        acceptance_criteria=[
            {"text": "done", "done": True},
            {"text": "also done", "done": True},
        ],
    )

    assert ticket.is_completable is True
