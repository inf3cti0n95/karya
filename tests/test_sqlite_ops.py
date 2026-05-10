import os
import shutil
from pathlib import Path
import pytest
from runnrr.sdk.client import RunnrrClient
from runnrr.core.models import TicketStatus, Priority, TicketType

@pytest.fixture
def clean_project(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    return project_root

def test_sqlite_init(clean_project):
    client = RunnrrClient(clean_project)
    client.init()
    db_path = clean_project / ".runnrr" / "runnrr.db"
    assert db_path.exists()
    
    # Check if we can create a ticket
    ticket = client.create_ticket("Test Ticket")
    assert ticket.id == "TICKET-001"
    assert ticket.title == "Test Ticket"
    
    # Check DB directly
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT title FROM tickets WHERE id='TICKET-001'").fetchone()
    assert row[0] == "Test Ticket"
    conn.close()

def test_sqlite_migration(clean_project):
    # 1. Setup v0.1.x files
    runnrr_dir = clean_project / ".runnrr"
    runnrr_dir.mkdir()
    
    tickets_dir = runnrr_dir / "tickets" / "backlog"
    tickets_dir.mkdir(parents=True)
    
    ticket_content = """---
id: TICKET-001
title: Old Ticket
status: backlog
priority: medium
type: feature
created_at: '2026-05-08T12:00:00Z'
updated_at: '2026-05-08T12:00:00Z'
---

## Goal
Legacy goal"""
    (tickets_dir / "TICKET-001.md").write_text(ticket_content, encoding="utf-8")
    
    # 2. Run migration
    client = RunnrrClient(clean_project)
    result = client.migrate()
    
    assert result["status"] == "success"
    assert result["counts"]["tickets"] == 1
    
    # 3. Verify in DB
    ticket = client.get_ticket("TICKET-001")
    assert ticket.title == "Old Ticket"
    assert ticket.goal_text == "Legacy goal"
    
    # 4. Verify archive
    assert (runnrr_dir / "archive_v01" / "tickets" / "backlog" / "TICKET-001.md").exists()
    assert not (tickets_dir / "TICKET-001.md").exists()

def test_bidirectional_links(clean_project):
    client = RunnrrClient(clean_project)
    client.init()
    ticket = client.create_ticket("Ticket 1")
    adr = client.create_adr("ADR 1", context="ctx", decision="dec")
    
    client.link(ticket.id, adr.id)
    
    # Check ticket side
    t = client.get_ticket(ticket.id)
    assert adr.id in t.linked_adrs

def test_event_log(clean_project):
    client = RunnrrClient(clean_project)
    client.init()
    client.create_ticket("Log test")
    
    events = client.list_events(limit=10)
    assert len(events) >= 1
    assert events[0]["event_type"] == "ticket.created"
