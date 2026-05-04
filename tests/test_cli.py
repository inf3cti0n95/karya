"""CLI tests."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from karya.cli.main import cli


def test_help_outputs_json() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert "commands" in payload


def test_help_outputs_human() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help", "--human"])

    assert result.exit_code == 0
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.output)
    assert "Commands" in result.output


def test_init_creates_dirs(tmp_path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0
        assert (Path(".karya")).exists()


def test_create_and_block(tmp_path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init"])
        result = runner.invoke(cli, ["create", "Test"])
        payload = json.loads(result.output)
        ticket_id = payload["ticket"]["id"]

        runner.invoke(cli, ["start", ticket_id, "--agent", "tester"])
        result = runner.invoke(cli, ["block", ticket_id, "reason"])
        payload = json.loads(result.output)
        assert payload["new_state"] == "blocked"
