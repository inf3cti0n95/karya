"""Integration tests for Phase A: Working Foundation."""

import pytest
from click.testing import CliRunner
from runnrr.cli.main import cli
from pathlib import Path
import json

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def temp_repo(tmp_path):
    d = tmp_path / "repo"
    d.mkdir()
    return d

def test_runnrr_lifecycle(runner, temp_repo):
    with runner.isolated_filesystem(temp_repo):
        # 1. runnrr init
        result = runner.invoke(cli, ["--json", "init"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert Path(".runnrr").exists()
        assert Path(".runnrr/tickets/backlog").exists()

        # 2. runnrr epic create
        result = runner.invoke(cli, ["--json", "epic", "create", "Main Epic", "--goal", "Finish everything"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        epic_id = data["epic"]["id"]
        assert epic_id == "EPIC-001"

        # 3. runnrr create
        result = runner.invoke(cli, ["--json", "create", "First Ticket", "--epic", epic_id, "--priority", "high"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        ticket_id = data["ticket"]["id"]
        assert ticket_id == "TICKET-001"

        # 4. runnrr list
        result = runner.invoke(cli, ["--json", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 1
        assert data["tickets"][0]["id"] == ticket_id

        # 5. runnrr start
        result = runner.invoke(cli, ["--json", "start", ticket_id])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["new_state"] == "in-progress"

        # 6. runnrr log
        result = runner.invoke(cli, ["--json", "log", ticket_id, "Working hard"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["message"] == "logged"

        # 7. runnrr describe
        result = runner.invoke(cli, ["--json", "describe", ticket_id])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ticket"]["id"] == ticket_id
        assert "Working hard" in str(data["ticket"]["execution_log"])

        # 8. runnrr done
        # Initially fail if acceptance criteria (if any) are not met.
        # But Phase A models might not enforce it yet unless they are in the md.
        result = runner.invoke(cli, ["--json", "done", ticket_id])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["new_state"] == "done"

def test_runnrr_adr_lifecycle(runner, temp_repo):
    with runner.isolated_filesystem(temp_repo):
        runner.invoke(cli, ["init"])
        
        # 1. runnrr adr create
        result = runner.invoke(cli, ["--json", "adr", "create", "Use SQLite", "--context", "Need a DB", "--decision", "SQLite"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        adr_id = data["adr"]["id"]
        assert adr_id == "ADR-001"

        # 2. runnrr adr accept
        result = runner.invoke(cli, ["--json", "adr", "accept", adr_id])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "accepted"

        # 3. runnrr adr list
        result = runner.invoke(cli, ["--json", "adr", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 1
        assert data["adrs"][0]["id"] == adr_id

        # 4. runnrr adr describe
        result = runner.invoke(cli, ["--json", "adr", "describe", adr_id])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["adr"]["id"] == adr_id
        assert data["adr"]["decision_text"] == "SQLite"

def test_runnrr_block(runner, temp_repo):
    with runner.isolated_filesystem(temp_repo):
        runner.invoke(cli, ["init"])
        runner.invoke(cli, ["create", "Blocked Ticket"])
        ticket_id = "TICKET-001"
        runner.invoke(cli, ["start", ticket_id])
        
        result = runner.invoke(cli, ["--json", "block", ticket_id, "Missing coffee"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["new_state"] == "blocked"
        assert data["reason"] == "Missing coffee"
