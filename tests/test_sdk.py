"""SDK tests."""

from pathlib import Path

import pytest

from karya.core.filesystem import KARYA_ROOT
from karya.exceptions import IncompleteAcceptanceCriteria
from karya.sdk.client import KaryaClient


def test_client_root_is_absolute(tmp_path: Path) -> None:
    client = KaryaClient(tmp_path)
    assert isinstance(client.root, Path)
    assert client.root.is_absolute()


def test_client_auto_init(tmp_path: Path) -> None:
    client = KaryaClient(tmp_path)
    assert (client.root / KARYA_ROOT).exists()


def test_sdk_lifecycle(tmp_path: Path) -> None:
    client = KaryaClient(tmp_path, agent="tester")
    ticket = client.create_ticket("Lifecycle")
    client.transition(ticket.id, "todo")
    client.transition(ticket.id, "in-progress")
    client.log(ticket.id, "Working")

    ticket = client.get_ticket(ticket.id)
    ticket.acceptance_criteria = [{"text": "AC", "done": False}]
    client._tickets._write_ticket(ticket)

    with pytest.raises(IncompleteAcceptanceCriteria):
        client.transition(ticket.id, "done")


def test_load_context(tmp_path: Path) -> None:
    client = KaryaClient(tmp_path)
    context = client.load_context()
    assert "System Architecture" in context
