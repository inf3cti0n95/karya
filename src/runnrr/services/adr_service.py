"""ADR service operations."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from runnrr.core.filesystem import (
	ADRS_DIR,
	find_adr_path,
	generate_id,
	init_runnrr,
	list_all_adrs,
	normalize_root,
	write_file,
)
from runnrr.core.models import ADR, ADRStatus, normalize_tag
from runnrr.core.parser import parse_adr, serialize_adr
from runnrr.git.integration import GitIntegration


class ADRService:
	def __init__(self, root: Path):
		self.root = normalize_root(root)
		self._git = GitIntegration(self.root)

	def create(
		self,
		title: str,
		context: str,
		decision: str,
		consequences: str = "",
		alternatives: str = "",
		linked_tickets: list[str] | None = None,
		linked_epics: list[str] | None = None,
		tags: list[str] | None = None,
		actor: str | None = None,
	) -> ADR:
		init_runnrr(self.root)

		adr_id = generate_id("adr", self.root)
		normalized_tags = [normalize_tag(t) for t in (tags or [])]
		
		adr = ADR(
			id=adr_id,
			title=title,
			status=ADRStatus.PROPOSED,
			date=date.today(),
			linked_tickets=linked_tickets or [],
			linked_epics=linked_epics or [],
			tags=normalized_tags,
			context_text=context,
			decision_text=decision,
			consequences_text=consequences,
			alternatives_text=alternatives,
		)

		path = self.root / ADRS_DIR / f"{adr_id}.md"
		adr.path = path
		self._save(adr)

		self._git.commit(f"runnrr: [{adr_id}] proposed ({actor or 'system'})")
		return adr

	def get(self, adr_id: str) -> ADR:
		path = find_adr_path(adr_id, self.root)
		if not path:
			raise Exception(f"ADR '{adr_id}' not found.")
		return parse_adr(path)

	def list(
		self,
		status: str | None = None,
		tag: str | None = None,
	) -> list[ADR]:
		adrs: list[ADR] = []
		for path in list_all_adrs(self.root):
			adrs.append(parse_adr(path))

		if status:
			adrs = [a for a in adrs if a.status == status]
		if tag:
			tag = normalize_tag(tag)
			adrs = [a for a in adrs if tag in a.tags]

		return adrs

	def update(self, adr_id: str, updates: dict, actor: str | None = None) -> ADR:
		adr = self.get(adr_id)
		for field, value in updates.items():
			if field == "tags" and isinstance(value, list):
				value = [normalize_tag(t) for t in value]
			if hasattr(adr, field):
				setattr(adr, field, value)
			else:
				raise Exception(f"Invalid field '{field}'")
		self._save(adr)
		self._git.commit(f"runnrr: [{adr_id}] updated ({actor or 'system'})")
		return adr

	def accept(self, adr_id: str, actor: str | None = None) -> ADR:
		adr = self.get(adr_id)
		if adr.status != ADRStatus.PROPOSED:
			raise Exception(f"Cannot accept ADR in status {adr.status}")
		
		adr.status = ADRStatus.ACCEPTED
		self._save(adr)
		self._git.commit(f"runnrr: [{adr_id}] accepted ({actor or 'system'})")
		return adr

	def describe(self, adr_id: str) -> dict:
		adr = self.get(adr_id)
		data = adr.model_dump(mode="json")
		if adr.path:
			data["path"] = str(adr.path)
		return data

	def _save(self, adr: ADR) -> None:
		if not adr.path:
			raise Exception("ADR path missing.")
		content = serialize_adr(adr)
		import frontmatter
		post = frontmatter.loads(content)
		write_file(adr.path, post.metadata, post.content)
