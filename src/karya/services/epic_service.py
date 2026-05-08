"""Epic service operations."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from karya.core.filesystem import (
	EPICS_DIR,
	find_epic_path,
	generate_id,
	init_karya,
	list_all_epics,
	normalize_root,
	write_file,
)
from karya.core.models import Epic, EpicStatus, EpicType, Priority, normalize_tag
from karya.core.parser import parse_epic, serialize_epic, parse_ticket
from karya.git.integration import GitIntegration
from karya.core.filesystem import TICKET_DIRS


class EpicService:
	def __init__(self, root: Path):
		self.root = normalize_root(root)
		self._git = GitIntegration(self.root)

	def create(
		self,
		title: str,
		goal: str = "",
		type: EpicType = EpicType.FEATURE,
		priority: Priority = Priority.MEDIUM,
		tags: list[str] | None = None,
		actor: str | None = None,
	) -> Epic:
		init_karya(self.root)

		epic_id = generate_id("epic", self.root)
		now = datetime.now(timezone.utc)
		normalized_tags = [normalize_tag(t) for t in (tags or [])]
		
		epic = Epic(
			id=epic_id,
			title=title,
			type=type,
			priority=priority,
			created_at=now,
			updated_at=now,
			tags=normalized_tags,
			goal_text=goal,
		)

		path = self.root / EPICS_DIR / f"{epic_id}.md"
		epic.path = path
		self._save(epic)

		self._git.commit(f"karya: [{epic_id}] created ({actor or 'system'})")
		return epic

	def get(self, epic_id: str) -> Epic:
		path = find_epic_path(epic_id, self.root)
		if not path:
			raise Exception(f"Epic '{epic_id}' not found.")
		return parse_epic(path)

	def list(
		self,
		tag: str | None = None,
	) -> list[Epic]:
		epics: list[Epic] = []
		for path in list_all_epics(self.root):
			epics.append(parse_epic(path))

		if tag:
			tag = normalize_tag(tag)
			epics = [e for e in epics if tag in e.tags]

		return epics

	def update(self, epic_id: str, updates: dict, actor: str | None = None) -> Epic:
		epic = self.get(epic_id)
		for field, value in updates.items():
			if field == "tags" and isinstance(value, list):
				value = [normalize_tag(t) for t in value]
			if hasattr(epic, field):
				setattr(epic, field, value)
			else:
				raise Exception(f"Invalid field '{field}'")

		self._save(epic)
		self._git.commit(f"karya: [{epic_id}] updated ({actor or 'system'})")
		return epic

	def describe(self, epic_id: str) -> dict:
		epic = self.get(epic_id)
		data = epic.model_dump(mode="json")
		
		# Compute status and progress
		tickets = self._get_epic_tickets(epic_id)
		if not tickets:
			data["status"] = "planned"
			data["progress"] = {"done": 0, "total": 0, "percent": 0}
		else:
			done = [t for t in tickets if t.status == "done"]
			total = len(tickets)
			percent = int((len(done) / total) * 100) if total > 0 else 0
			data["progress"] = {"done": len(done), "total": total, "percent": percent}
			
			if all(t.status == "done" for t in tickets):
				data["status"] = "done"
			elif any(t.status in ["in-progress", "done"] for t in tickets):
				data["status"] = "active"
			else:
				data["status"] = "planned"
		
		if epic.path:
			data["path"] = str(epic.path)
		return data

	def _get_epic_tickets(self, epic_id: str):
		tickets = []
		for status_dir in TICKET_DIRS.values():
			for path in (self.root / status_dir).glob("*.md"):
				ticket = parse_ticket(path)
				if ticket.epic == epic_id:
					tickets.append(ticket)
		return tickets

	def _save(self, epic: Epic) -> None:
		if not epic.path:
			raise Exception("Epic path missing.")
		content = serialize_epic(epic)
		import frontmatter
		post = frontmatter.loads(content)
		write_file(epic.path, post.metadata, post.content)
