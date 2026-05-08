"""Tests for Phase B: Next and Context."""

import pytest
import json
from pathlib import Path
from click.testing import CliRunner
from runnrr.cli.main import cli
from runnrr.sdk.client import RunnrrClient
from runnrr.core.models import TicketStatus, Priority, TicketType, EpicType, ADRStatus

@pytest.fixture
def runner():
    return CliRunner()

def test_next_ticket_logic(runner, tmp_path):
    with runner.isolated_filesystem(tmp_path):
        runner.invoke(cli, ["--json", "init"])
        client = RunnrrClient(".")
        
        # T1: low priority, effort 1, todo
        t1 = client.create_ticket("T1", priority=Priority.LOW, estimated_effort=1)
        client.transition(t1.id, "todo")
        
        # T2: high priority, effort 5, todo
        t2 = client.create_ticket("T2", priority=Priority.HIGH, estimated_effort=5)
        client.transition(t2.id, "todo")
        
        # T3: critical priority, effort 1, todo
        t3 = client.create_ticket("T3", priority=Priority.CRITICAL, estimated_effort=1)
        client.transition(t3.id, "todo")
        
        # T4: critical priority, effort 1, backlog
        t4 = client.create_ticket("T4", priority=Priority.CRITICAL, estimated_effort=1)
        
        # Next should be T3 (critical, low effort, todo)
        result = runner.invoke(cli, ["--json", "next"])
        if result.exit_code != 0:
            print("NEXT FAILED:", result.output, result.exception)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ticket"]["id"] == t3.id
        
        # Now add a blocker to T3
        client.update_ticket(t3.id, {"blocked_by": [t2.id]})
        
        # Next should be T2 (high, effort 5, todo) because T3 is blocked by a non-done ticket
        result = runner.invoke(cli, ["--json", "next"])
        data = json.loads(result.output)
        assert data["ticket"]["id"] == t2.id

def test_context_logic(runner, tmp_path):
    with runner.isolated_filesystem(tmp_path):
        runner.invoke(cli, ["--json", "init"])
        client = RunnrrClient(".")
        
        # Create an epic
        epic = client.create_epic("Epic 1", goal="Epic Goal")
        
        # Create a blocker
        blocker = client.create_ticket("Blocker")
        
        # Create the main ticket
        ticket = client.create_ticket("Main", epic=epic.id, tags=["auth"])
        client.update_ticket(ticket.id, {"blocked_by": [blocker.id]})
        
        # Create an ADR linked directly
        adr1 = client.create_adr("ADR 1", context="C", decision="D", linked_tickets=[ticket.id])
        client.accept_adr(adr1.id)
        
        # Create an ADR matching tags
        adr2 = client.create_adr("ADR 2", context="C", decision="D", tags=["auth"])
        client.accept_adr(adr2.id)
        
        result = runner.invoke(cli, ["--json", "context", ticket.id])
        print("CONTEXT OUTPUT LENGTH:", len(result.output))
        print("CONTEXT OUTPUT REPR:", repr(result.output))
        if result.exit_code != 0:
            print("CONTEXT ERROR:", result.exception)
        assert result.exit_code == 0
        data = json.loads(result.output)
        
        sections = data["sections"]
        types = [s["type"] for s in sections]
        
        # The exact order depends on scoring, but should include ticket, blocker, direct adr, epic, tag adr, convention
        assert "ticket" in types
        assert "blocker" in types
        assert "direct_adr" in types
        assert "epic" in types
        assert "tag_adr" in types
        assert "convention" in types
