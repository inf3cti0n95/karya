"""Tests for Phase D: valid_actions and Agent Interface."""

import pytest
import json
from pathlib import Path
from click.testing import CliRunner
from runnrr.cli.main import cli
from runnrr.sdk.client import RunnrrClient

@pytest.fixture
def runner():
    return CliRunner()

def test_valid_actions_todo(runner, tmp_path):
    with runner.isolated_filesystem(tmp_path):
        runner.invoke(cli, ["--json", "init"])
        client = RunnrrClient(".")
        t1 = client.create_ticket("T1")
        client.transition(t1.id, "todo")
        
        result = runner.invoke(cli, ["--json", "actions", t1.id])
        assert result.exit_code == 0
        data = json.loads(result.output)
        
        assert data["ticket_id"] == t1.id
        assert data["state"] == "todo"
        
        available_actions = [a["action"] for a in data["available"] if a.get("available", True)]
        assert "start_ticket" in available_actions
        assert "create_ticket" in available_actions
        assert "log_ticket" not in available_actions
        assert "done_ticket" not in available_actions

def test_valid_actions_blocked_start(runner, tmp_path):
    with runner.isolated_filesystem(tmp_path):
        runner.invoke(cli, ["--json", "init"])
        client = RunnrrClient(".")
        b1 = client.create_ticket("B1")
        client.transition(b1.id, "todo")
        t1 = client.create_ticket("T1")
        client.update_ticket(t1.id, {"blocked_by": [b1.id]})
        client.transition(t1.id, "todo")
        
        result = runner.invoke(cli, ["--json", "actions", t1.id])
        assert result.exit_code == 0
        data = json.loads(result.output)
        
        start_action = next(a for a in data["available"] if a["action"] == "start_ticket")
        assert not start_action.get("available", True)
        assert len(start_action.get("blocked_by", [])) == 1

def test_valid_actions_in_progress(runner, tmp_path):
    with runner.isolated_filesystem(tmp_path):
        runner.invoke(cli, ["--json", "init"])
        client = RunnrrClient(".")
        t1 = client.create_ticket("T1")
        client.transition(t1.id, "todo")
        client.transition(t1.id, "in-progress")
        
        t1_reloaded = client.get_ticket(t1.id)
        t1_reloaded.acceptance_criteria = [{"text": "AC1", "done": False}]
        client._tickets._save(t1_reloaded)
        
        result = runner.invoke(cli, ["--json", "actions", t1.id])
        assert result.exit_code == 0
        data = json.loads(result.output)
        
        available_actions = [a["action"] for a in data["available"] if a.get("available", True)]
        assert "log_ticket" in available_actions
        assert "block_ticket" in available_actions
        
        done_action = next(a for a in data["available"] if a["action"] == "done_ticket")
        assert not done_action.get("available", True)
        assert "AC1" in done_action.get("blocked_by", [])[0]

def test_runnrr_exec(runner, tmp_path):
    with runner.isolated_filesystem(tmp_path):
        runner.invoke(cli, ["--json", "init"])
        client = RunnrrClient(".")
        t1 = client.create_ticket("T1")
        client.transition(t1.id, "todo")
        
        result = runner.invoke(cli, ["--json", "exec", t1.id])
        assert result.exit_code == 0
        data = json.loads(result.output)
        
        assert "ticket" in data
        assert "context" in data
        assert "valid_actions" in data
        assert "suggested_command" in data
        
        assert data["ticket"]["id"] == t1.id
        assert data["suggested_command"] == f"runnrr start {t1.id}"
