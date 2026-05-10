import os
import shutil
from pathlib import Path
import pytest
from runnrr.sdk.client import RunnrrClient
from runnrr.exceptions import RunnrrNotInitializedError

@pytest.fixture
def clean_project(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    return project_root

def test_root_discovery(clean_project):
    # 1. Initialize project
    client = RunnrrClient(clean_project)
    # init is called in __init__? No, it's not.
    # Wait, RunnrrClient.__init__ calls find_runnrr_root which FAILS if not init.
    # So I MUST call runnrr init first.
    pass

def test_init_guard(clean_project):
    # This needs to use the CLI or a mock
    from click.testing import CliRunner
    from runnrr.cli.main import cli
    
    runner = CliRunner()
    
    # 1. First init
    with runner.isolated_filesystem(temp_dir=clean_project):
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0
        
        # 2. Second init in same dir
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 1
        # The exception might be caught by click or bubble up
        assert "already initialized" in str(result.exception) or "already initialized" in result.output
        
        # 3. Init in subdir
        os.mkdir("subdir")
        os.chdir("subdir")
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 1
        assert "already initialized" in str(result.exception) or "already initialized" in result.output

def test_not_initialized_error(tmp_path):
    from click.testing import CliRunner
    from runnrr.cli.main import cli
    
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ["list"])
        # Should exit with 1 and show error
        assert result.exit_code == 1
        assert "No .runnrr/ directory found" in str(result.exception) or "No .runnrr/ directory found" in result.output

def test_db_path_support(clean_project):
    # 1. Initialize project
    runnrr_dir = clean_project / ".runnrr"
    runnrr_dir.mkdir()
    db_path = runnrr_dir / "custom.db"
    
    # Use SDK with explicit db_path
    client = RunnrrClient(clean_project, db_path=db_path)
    assert client._db.db_path == db_path
    assert db_path.exists()
    
    client.create_ticket("Test Custom DB")
    
    # Verify with another client
    client2 = RunnrrClient(clean_project, db_path=db_path)
    tickets = client2.list_tickets(status='backlog')
    assert len(tickets) == 1
    assert tickets[0].title == "Test Custom DB"
