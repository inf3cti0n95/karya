"""Epic service tests."""

from pathlib import Path

import pytest

from karya.core.models import EpicStatus, TicketStatus
from karya.exceptions import EpicArchivedError, UpdateForbiddenError
from karya.services.epic_service import EpicService
from karya.services.ticket_service import TicketService


def test_create_writes_epic(karya_root: Path) -> None:
    service = EpicService(karya_root)
    epic = service.create("Auth")
    assert epic.id.startswith("EPIC-")
    assert epic.path is not None
    assert epic.path.exists()


def test_status_active_when_in_progress(karya_root: Path) -> None:
    tickets = TicketService(karya_root)
    epic_service = EpicService(karya_root)

    ticket = tickets.create("Ticket")
    tickets.transition(ticket.id, "todo")
    tickets.transition(ticket.id, "in-progress")

    epic = epic_service.create("Epic")
    epic_service.link_ticket(epic.id, ticket.id)

    loaded = epic_service.get(epic.id)
    assert loaded.status == EpicStatus.ACTIVE


def test_status_done_when_all_done(karya_root: Path) -> None:
    tickets = TicketService(karya_root)
    epic_service = EpicService(karya_root)

    ticket = tickets.create("Ticket")
    tickets.transition(ticket.id, "todo")
    tickets.transition(ticket.id, "in-progress")

    ticket = tickets.get(ticket.id)
    ticket.acceptance_criteria = [{"text": "AC", "done": True}]
    tickets._write_ticket(ticket)
    tickets.transition(ticket.id, "done")

    epic = epic_service.create("Epic")
    epic_service.link_ticket(epic.id, ticket.id)

    loaded = epic_service.get(epic.id)
    assert loaded.status == EpicStatus.DONE


def test_progress_computed(karya_root: Path) -> None:
    tickets = TicketService(karya_root)
    epic_service = EpicService(karya_root)

    ticket1 = tickets.create("Ticket 1")
    ticket2 = tickets.create("Ticket 2")
    tickets.transition(ticket1.id, "todo")
    tickets.transition(ticket1.id, "in-progress")

    ticket1 = tickets.get(ticket1.id)
    ticket1.acceptance_criteria = [{"text": "AC", "done": True}]
    tickets._write_ticket(ticket1)
    tickets.transition(ticket1.id, "done")

    epic = epic_service.create("Epic")
    epic_service.link_ticket(epic.id, ticket1.id)
    epic_service.link_ticket(epic.id, ticket2.id)

    loaded = epic_service.get(epic.id)
    assert loaded.progress == {"done": 1, "total": 2, "pct": 50}


def test_link_ticket_updates_ticket(karya_root: Path) -> None:
    tickets = TicketService(karya_root)
    epic_service = EpicService(karya_root)

    ticket = tickets.create("Ticket")
    epic = epic_service.create("Epic")
    epic_service.link_ticket(epic.id, ticket.id)

    updated = tickets.get(ticket.id)
    assert updated.epic == epic.id


def test_update_forbidden_field(karya_root: Path) -> None:
    epic_service = EpicService(karya_root)
    epic = epic_service.create("Epic")

    with pytest.raises(UpdateForbiddenError):
        epic_service.update(epic.id, {"id": "EPIC-999"})


def test_archive_blocks_updates(karya_root: Path) -> None:
    epic_service = EpicService(karya_root)
    epic = epic_service.create("Epic")
    epic_service.archive(epic.id, "done")

    with pytest.raises(EpicArchivedError):
        epic_service.update(epic.id, {"title": "New"})
