"""Shared pytest fixtures for Runnrr."""

import os
from pathlib import Path
import pytest
from runnrr import RunnrrClient
from runnrr.core.db import Database

@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
	"""A clean project directory."""
	project = tmp_path / "project"
	project.mkdir()
	return project

@pytest.fixture
def client(project_dir: Path) -> RunnrrClient:
	"""A properly initialized RunnrrClient."""
	# We need to change CWD to make find_runnrr_root work in some cases,
	# or just pass the explicit path.
	old_cwd = os.getcwd()
	os.chdir(project_dir)
	try:
		client = RunnrrClient(root=project_dir, agent="test-agent")
		client.init()
		return client
	finally:
		os.chdir(old_cwd)

@pytest.fixture
def db(client: RunnrrClient) -> Database:
	"""The underlying Database object."""
	return client._db

@pytest.fixture
def runnrr_root(client: RunnrrClient) -> Path:
	"""The project root Path (for backward compatibility)."""
	return client.root
