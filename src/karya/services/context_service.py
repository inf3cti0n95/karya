"""Context loading and merging."""

from __future__ import annotations

from pathlib import Path

from karya.core.filesystem import load_context_files, normalize_root


class ContextService:
	def __init__(self, root: Path):
		self.root = normalize_root(root)

	def load(self) -> str:
		return load_context_files(self.root)
