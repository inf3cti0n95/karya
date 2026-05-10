"""CLI tests for human-readable output and error conditions using SQLite."""

import pytest
from click.testing import CliRunner
from runnrr.cli.main import cli
import json

@pytest.fixture
def runner():
    return CliRunner()

def test_cli_describe_non_existent(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["init"])
        result = runner.invoke(cli, ["describe", "TICKET-999"])
        assert "Error" in result.output or "NOT_FOUND" in result.output
        assert result.exit_code != 0

def test_cli_list_filters(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["init"])
        runner.invoke(cli, ["epic", "create", "E1"])
        runner.invoke(cli, ["create", "T1", "--tag", "tag1", "--epic", "EPIC-001"])
        runner.invoke(cli, ["create", "T2", "--tag", "tag2"])
        
        # Filter by tag (use --status all since they are in backlog)
        result = runner.invoke(cli, ["--json", "list", "--tag", "tag1", "--status", "all"])
        data = json.loads(result.output)
        assert data["count"] == 1
        assert data["tickets"][0]["title"] == "T1"
        
        # Filter by epic
        result = runner.invoke(cli, ["--json", "list", "--epic", "EPIC-001", "--status", "all"])
        data = json.loads(result.output)
        assert data["count"] == 1
        assert data["tickets"][0]["title"] == "T1"

def test_cli_block_and_log(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["init"])
        runner.invoke(cli, ["create", "T1"])
        runner.invoke(cli, ["start", "TICKET-001"])
        
        # Log
        result = runner.invoke(cli, ["--json", "log", "TICKET-001", "Some progress"])
        data = json.loads(result.output)
        assert data["message"] == "logged"
        
        # Block
        result = runner.invoke(cli, ["--json", "block", "TICKET-001", "The reason"])
        data = json.loads(result.output)
        assert data["new_state"] == "blocked"

def test_cli_epic_lifecycle(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["init"])
        runner.invoke(cli, ["--json", "epic", "create", "E1", "--goal", "G1"])
        data = json.loads(runner.invoke(cli, ["--json", "epic", "list"]).output)
        assert data["count"] == 1
        
        result = runner.invoke(cli, ["--json", "epic", "describe", "EPIC-001"])
        data = json.loads(result.output)
        assert data["epic"]["goal_text"] == "G1"

def test_cli_adr_lifecycle(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["init"])
        runner.invoke(cli, ["--json", "adr", "create", "A1", "--context", "C1", "--decision", "D1"])
        
        result = runner.invoke(cli, ["--json", "adr", "list"])
        data = json.loads(result.output)
        assert data["count"] == 1
        
        runner.invoke(cli, ["--json", "adr", "accept", "ADR-001"])
        result = runner.invoke(cli, ["--json", "adr", "describe", "ADR-001"])
        data = json.loads(result.output)
        assert data["adr"]["status"] == "accepted"
