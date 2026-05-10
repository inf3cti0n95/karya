"""Tests for the runnrr update command and task/AC management."""

import pytest
from click.testing import CliRunner
from runnrr.cli.main import cli
from runnrr.sdk.client import RunnrrClient

def test_update_ticket_goal_and_notes(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["init"])
        runner.invoke(cli, ["create", "Test Ticket"])
        
        # Update goal and notes
        result = runner.invoke(cli, ["update", "TICKET-001", "--goal", "My new goal", "--notes", "Some notes"])
        assert result.exit_code == 0
        
        # Verify via describe
        result = runner.invoke(cli, ["--json", "describe", "TICKET-001"])
        import json
        data = json.loads(result.output)
        assert data["ticket"]["goal_text"] == "My new goal"
        assert data["ticket"]["notes_text"] == "Some notes"

def test_manage_tasks_via_cli(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["init"])
        runner.invoke(cli, ["create", "Task Test"])
        
        # Add tasks
        runner.invoke(cli, ["update", "TICKET-001", "--add-task", "Task 1"])
        runner.invoke(cli, ["update", "TICKET-001", "--add-task", "Task 2"])
        
        # Check task 0
        runner.invoke(cli, ["update", "TICKET-001", "--check-task", "0"])
        
        # Verify
        result = runner.invoke(cli, ["--json", "describe", "TICKET-001"])
        import json
        data = json.loads(result.output)
        tasks = data["ticket"]["tasks"]
        assert len(tasks) == 2
        assert tasks[0]["text"] == "Task 1"
        assert tasks[0]["done"] is True
        assert tasks[1]["text"] == "Task 2"
        assert tasks[1]["done"] is False

def test_manage_ac_via_cli(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["init"])
        runner.invoke(cli, ["create", "AC Test"])
        
        # Add AC
        runner.invoke(cli, ["update", "TICKET-001", "--add-ac", "AC 1"])
        
        # Try to finish ticket (should fail)
        runner.invoke(cli, ["start", "TICKET-001"])
        result = runner.invoke(cli, ["done", "TICKET-001"])
        assert result.exit_code != 0
        
        # Check AC
        runner.invoke(cli, ["update", "TICKET-001", "--check-ac", "0"])
        
        # Try to finish ticket (should succeed)
        result = runner.invoke(cli, ["done", "TICKET-001"])
        assert result.exit_code == 0
