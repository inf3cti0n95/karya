"""Tests for Phase C: Search, Tags, and Links using SQLite."""

import pytest
import json
from pathlib import Path
from click.testing import CliRunner
from runnrr.cli.main import cli
from runnrr.sdk.client import RunnrrClient
from runnrr.core.models import Priority

@pytest.fixture
def runner():
    return CliRunner()

def test_tag_normalization(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["--json", "init"])
        client = RunnrrClient(".")
        
        # Create ticket with weird tags
        t1 = client.create_ticket("T1", tags=["Auth Service", "JWT_token", "api@#$!"])
        
        # Reload and check normalization
        t1_reloaded = client.get_ticket(t1.id)
        assert "auth-service" in t1_reloaded.tags
        assert "jwt-token" in t1_reloaded.tags
        assert "api" in t1_reloaded.tags
        assert "Auth Service" not in t1_reloaded.tags

def test_search_and_rebuild(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["--json", "init"])
        client = RunnrrClient(".")
        
        client.create_ticket("JWT authentication", goal="Implement JWT login")
        client.create_epic("Auth & Authorization", goal="Secure stateless auth")
        adr = client.create_adr("Use JWT", context="Need stateless", decision="Use JWT access tokens")
        client.accept_adr(adr.id)
        
        # Build index implicitly or explicitly
        runner.invoke(cli, ["--json", "index", "rebuild"])
        
        # Search for JWT
        result = runner.invoke(cli, ["--json", "search", "JWT"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        
        assert data["count"] == 2
        types = [res["type"] for res in data["results"]]
        assert "ticket" in types
        assert "adr" in types
        
def test_find_related(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["--json", "init"])
        client = RunnrrClient(".")
        
        t1 = client.create_ticket("T1", tags=["auth", "jwt"])
        t2 = client.create_ticket("T2", tags=["auth", "database"])
        adr1 = client.create_adr("A1", context="C", decision="D", tags=["auth", "jwt", "backend"])
        
        runner.invoke(cli, ["--json", "index", "rebuild"])
        
        result = runner.invoke(cli, ["--json", "find-related", t1.id])
        assert result.exit_code == 0
        data = json.loads(result.output)
        
        # adr1 has 2 overlapping tags (auth, jwt), t2 has 1 overlapping tag (auth)
        # so adr1 should be first, t2 second
        assert len(data["results"]) >= 2
        ids = [res["id"] for res in data["results"]]
        assert adr1.id in ids
        assert t2.id in ids

def test_linking(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["--json", "init"])
        client = RunnrrClient(".")
        
        t1 = client.create_ticket("T1")
        adr1 = client.create_adr("A1", context="C", decision="D")
        epic1 = client.create_epic("E1")
        
        # Link ticket to ADR
        result = runner.invoke(cli, ["--json", "link", t1.id, adr1.id])
        assert result.exit_code == 0
        
        # Verify bidirectional
        t1_reloaded = client.get_ticket(t1.id)
        adr1_reloaded = client.get_adr(adr1.id)
        
        assert adr1.id in t1_reloaded.linked_adrs
        assert t1.id in adr1_reloaded.linked_tickets
        
        # Link ticket to Epic
        runner.invoke(cli, ["--json", "link", t1.id, epic1.id])
        t1_reloaded = client.get_ticket(t1.id)
        assert t1_reloaded.epic == epic1.id
        
        # Link ADR to Epic
        runner.invoke(cli, ["--json", "link", adr1.id, epic1.id])
        adr1_reloaded = client.get_adr(adr1.id)
        epic1_reloaded = client.get_epic(epic1.id)
        assert epic1.id in adr1_reloaded.linked_epics
        assert adr1.id in epic1_reloaded.linked_adrs
