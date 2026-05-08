"""Git integration layer."""

from __future__ import annotations

from pathlib import Path

from git import InvalidGitRepositoryError, Repo

from runnrr.core.filesystem import normalize_root


class GitIntegration:
	def __init__(self, root: Path):
		self.root = normalize_root(root)
		self._repo: Repo | None = None

	def ensure_repo(self) -> Repo:
		if self._repo is not None:
			return self._repo

		try:
			self._repo = Repo(self.root)
		except InvalidGitRepositoryError:
			self._repo = Repo.init(self.root)

		return self._repo

	def commit(self, message: str) -> None:
		repo = self.ensure_repo()
		repo.index.add([".runnrr"])

		if not repo.is_dirty(untracked_files=True):
			return

		repo.index.commit(f"runnrr: {message}")

	def is_available(self) -> bool:
		try:
			self.ensure_repo()
		except Exception:
			return False
		return True
