"""CLI tests for error branches using JSON output."""

import pytest
import json
from click.testing import CliRunner
from runnrr.cli.main import cli
from runnrr.core.models import TicketStatus

@pytest.fixture
def runner():
    return CliRunner()

def test_cli_create_invalid_type(runner, tmp_path):
    with runner.isolated_filesystem(tmp_path):
        runner.invoke(cli, ["init"])
        result = runner.invoke(cli, ["--json", "create", "T1", "--type", "invalid-type"])
        data = json.loads(result.output)
        assert data["status"] == "error"
        assert data["code"] == "INVALID_OPTION"

def test_cli_epic_create_invalid_priority(runner, tmp_path):
    with runner.isolated_filesystem(tmp_path):
        runner.invoke(cli, ["init"])
        result = runner.invoke(cli, ["--json", "epic", "create", "E1", "--priority", "super-high"])
        data = json.loads(result.output)
        assert data["status"] == "error"
        assert data["code"] == "INVALID_OPTION"

def test_cli_start_not_found(runner, tmp_path):
    with runner.isolated_filesystem(tmp_path):
        runner.invoke(cli, ["init"])
        result = runner.invoke(cli, ["--json", "start", "TICKET-999"])
        data = json.loads(result.output)
        assert data["status"] == "error"
        assert data["code"] == "NOT_FOUND"

def test_cli_start_invalid_transition(runner, tmp_path):
    with runner.isolated_filesystem(tmp_path):
        runner.invoke(cli, ["--json", "init"])
        r2 = runner.invoke(cli, ["--json", "create", "T1"])
        ticket_id = json.loads(r2.output)["ticket"]["id"]
        runner.invoke(cli, ["--json", "start", ticket_id])
        runner.invoke(cli, ["--json", "done", ticket_id])
        
        result = runner.invoke(cli, ["--json", "block", ticket_id, "reason"])
        data = json.loads(result.output)
        assert data["status"] == "error"

def test_cli_done_incomplete_ac(runner, tmp_path):
    with runner.isolated_filesystem(tmp_path):
        r1 = runner.invoke(cli, ["--json", "init"])
        assert json.loads(r1.output)["status"] == "ok"
        
        r2 = runner.invoke(cli, ["--json", "create", "T1"])
        assert json.loads(r2.output)["status"] == "ok"
        ticket_id = json.loads(r2.output)["ticket"]["id"]
        
        r3 = runner.invoke(cli, ["--json", "start", ticket_id])
        assert json.loads(r3.output)["status"] == "ok"
        
        # Manually add an incomplete AC
        from runnrr.sdk.client import RunnrrClient
        c = RunnrrClient(".")
        t = c.get_ticket(ticket_id)
        t.acceptance_criteria = [{"text": "AC1", "done": False}]
        c._tickets._save(t)
        
        result = runner.invoke(cli, ["--json", "done", ticket_id])
        data = json.loads(result.output)
        assert data["status"] == "error"
        assert data["code"] == "INCOMPLETE_CRITERIA"

def test_cli_adr_accept_failed(runner, tmp_path):
    with runner.isolated_filesystem(tmp_path):
        runner.invoke(cli, ["init"])
        runner.invoke(cli, ["adr", "create", "A1", "--context", "C", "--decision", "D"])
        runner.invoke(cli, ["adr", "accept", "ADR-001"])
        
        # Try accepting an already accepted ADR
        result = runner.invoke(cli, ["--json", "adr", "accept", "ADR-001"])
        data = json.loads(result.output)
        assert data["status"] == "error"
        assert data["code"] == "ACCEPT_FAILED"

def test_cli_describe_not_found(runner, tmp_path):
    with runner.isolated_filesystem(tmp_path):
        runner.invoke(cli, ["init"])
        for cmd in ["describe", "epic describe", "adr describe"]:
            parts = ["--json"] + cmd.split() + ["ID-999"]
            result = runner.invoke(cli, parts)
            data = json.loads(result.output)
            assert data["status"] == "error"
            assert data["code"] == "NOT_FOUND"

def test_cli_log_error(runner, tmp_path):
     with runner.isolated_filesystem(tmp_path):
        runner.invoke(cli, ["init"])
        result = runner.invoke(cli, ["--json", "log", "TICKET-999", "msg"])
        data = json.loads(result.output)
        assert data["status"] == "error"
