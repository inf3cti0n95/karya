"""Unit tests for the new Phase A filesystem operations."""

import pytest
from pathlib import Path
from karya.core.filesystem import (
    init_karya, 
    generate_id, 
    find_ticket_path, 
    list_tickets_in_state,
    TICKET_DIRS,
    EPICS_DIR,
    ADRS_DIR
)

def test_init_karya(tmp_path):
    init_karya(tmp_path)
    assert (tmp_path / ".karya").exists()
    assert (tmp_path / ".karya/tickets/backlog").exists()
    assert (tmp_path / ".karya/epics").exists()
    assert (tmp_path / ".karya/adrs").exists()
    assert (tmp_path / ".karya/context/conventions.md").exists()

def test_generate_id(tmp_path):
    init_karya(tmp_path)
    # Tickets
    assert generate_id("ticket", tmp_path) == "TICKET-001"
    (tmp_path / TICKET_DIRS["backlog"] / "TICKET-001.md").touch()
    assert generate_id("ticket", tmp_path) == "TICKET-002"
    
    # Epics
    assert generate_id("epic", tmp_path) == "EPIC-001"
    (tmp_path / EPICS_DIR / "EPIC-001.md").touch()
    assert generate_id("epic", tmp_path) == "EPIC-002"
    
    # ADRs
    assert generate_id("adr", tmp_path) == "ADR-001"
    (tmp_path / ADRS_DIR / "ADR-001.md").touch()
    assert generate_id("adr", tmp_path) == "ADR-002"

def test_find_ticket_path(tmp_path):
    init_karya(tmp_path)
    path = tmp_path / TICKET_DIRS["in-progress"] / "TICKET-005.md"
    path.touch()
    
    found = find_ticket_path("TICKET-005", tmp_path)
    assert found == path
    assert find_ticket_path("TICKET-999", tmp_path) is None

def test_list_tickets_in_state(tmp_path):
    init_karya(tmp_path)
    (tmp_path / TICKET_DIRS["todo"] / "TICKET-001.md").touch()
    (tmp_path / TICKET_DIRS["todo"] / "TICKET-002.md").touch()
    
    tickets = list_tickets_in_state("todo", tmp_path)
    assert len(tickets) == 2
    assert tickets[0].name == "TICKET-001.md"
