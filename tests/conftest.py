"""Shared pytest fixtures for Runnrr."""

from pathlib import Path

import pytest

from runnrr import RunnrrClient


@pytest.fixture
def runnrr_root(tmp_path: Path) -> Path:
	root = tmp_path / ".runnrr"
	client = RunnrrClient(root=root)
	client.init()
	return root


@pytest.fixture
def client(runnrr_root: Path) -> RunnrrClient:
	return RunnrrClient(root=runnrr_root, agent="test-agent")
