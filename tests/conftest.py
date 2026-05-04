"""Shared pytest fixtures for Karya."""

from pathlib import Path

import pytest

from karya import KaryaClient


@pytest.fixture
def karya_root(tmp_path: Path) -> Path:
	root = tmp_path / ".karya"
	client = KaryaClient(root=root)
	client.init()
	return root


@pytest.fixture
def client(karya_root: Path) -> KaryaClient:
	return KaryaClient(root=karya_root, agent="test-agent")
