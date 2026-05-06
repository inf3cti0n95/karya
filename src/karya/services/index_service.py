"""Index service for tags and full-text search."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from karya.core.filesystem import (
	ADRS_DIR,
	EPICS_DIR,
	INDEX_DIR,
	TICKET_DIRS,
	normalize_root,
)
from karya.core.models import SearchResultItem, SearchResults
from karya.core.parser import parse_adr, parse_epic, parse_ticket
from karya.exceptions import IndexError as KaryaIndexError


def normalize_tag(tag: str) -> str:
	"""
	1. Lowercase
	2. Strip leading/trailing whitespace
	3. Replace spaces and underscores with hyphens
	4. Remove characters that are not alphanumeric or hyphen
	5. Collapse consecutive hyphens
	"""
	t = tag.lower().strip()
	t = t.replace(" ", "-").replace("_", "-")
	t = re.sub(r"[^a-z0-9-]", "", t)
	t = re.sub(r"-+", "-", t)
	return t.strip("-")


class IndexService:
	def __init__(self, root: Path):
		self.root = normalize_root(root)
		self._index_dir = self.root / INDEX_DIR
		self._db_path = self._index_dir / "search.db"
		self._tags_path = self._index_dir / "tags.json"

	def _get_db(self) -> sqlite3.Connection:
		self._index_dir.mkdir(parents=True, exist_ok=True)
		db = sqlite3.connect(self._db_path)
		db.row_factory = sqlite3.Row
		return db

	def _init_db(self, db: sqlite3.Connection) -> None:
		db.execute("DROP TABLE IF EXISTS search_index")
		db.execute(
			"""
			CREATE VIRTUAL TABLE search_index USING fts5(
				entity_type,
				entity_id,
				title,
				body,
				tags,
				status,
				updated_at
			)
			"""
		)
		db.commit()

	def rebuild(self) -> dict:
		"""Full rebuild of both indexes from source files."""
		db = self._get_db()
		self._init_db(db)

		tags_index: Dict[str, List[Dict[str, str]]] = {}
		count = 0

		# Index Tickets
		for status_dir in TICKET_DIRS.values():
			for path in (self.root / status_dir).glob("TICKET-*.md"):
				try:
					ticket = parse_ticket(path)
					self._index_entity(db, "ticket", ticket.id, ticket.title, self._get_ticket_body(ticket), ticket.labels, ticket.status.value, ticket.updated_at, tags_index)
					count += 1
				except Exception:
					continue

		# Index Epics
		for path in (self.root / EPICS_DIR).glob("EPIC-*.md"):
			try:
				epic = parse_epic(path)
				# Epic status is computed in service, but we might store it if we can
				# For now, just use ARCHIVED if set, otherwise maybe compute?
				# The requirement says status is computed. 
				# Let's just leave status as None or computed value if possible.
				self._index_entity(db, "epic", epic.id, epic.title, self._get_epic_body(epic), epic.tags, epic.status.value if epic.status else "planned", epic.updated_at, tags_index)
				count += 1
			except Exception:
				continue

		# Index ADRs
		for path in (self.root / ADRS_DIR).glob("ADR-*.md"):
			try:
				adr = parse_adr(path)
				self._index_entity(db, "adr", adr.id, adr.title, self._get_adr_body(adr), adr.tags, adr.status.value, datetime.combine(adr.date, datetime.min.time()), tags_index)
				count += 1
			except Exception:
				continue

		# Index Context files (as 'context' entity type)
		context_dir = self.root / "context"
		if context_dir.exists():
			for path in context_dir.glob("*.md"):
				try:
					content = path.read_text(encoding="utf-8")
					# Simple parsing for context files
					title = path.stem
					self._index_entity(db, "context", path.stem, title, content, [], "active", datetime.fromtimestamp(path.stat().st_mtime), tags_index)
					count += 1
				except Exception:
					continue

		db.commit()
		db.close()

		with open(self._tags_path, "w", encoding="utf-8") as f:
			json.dump(tags_index, f, indent=2)

		return {"indexed": count, "tags": len(tags_index)}

	def _index_entity(self, db: sqlite3.Connection, entity_type: str, entity_id: str, title: str, body: str, tags: list[str], status: str, updated_at: datetime, tags_index: dict) -> None:
		norm_tags = [normalize_tag(t) for t in tags]
		tags_str = " ".join(norm_tags)
		
		db.execute(
			"INSERT INTO search_index (entity_type, entity_id, title, body, tags, status, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
			(entity_type, entity_id, title, body, tags_str, status, updated_at.isoformat())
		)

		for t in norm_tags:
			tags_index.setdefault(t, []).append({"type": entity_type, "id": entity_id})

	def _get_ticket_body(self, ticket: Any) -> str:
		parts = [
			ticket.context_text or "",
			ticket.goal_text or "",
			ticket.scope_text or "",
			"\n".join([t["text"] for t in ticket.tasks]),
			"\n".join([ac["text"] for ac in ticket.acceptance_criteria]),
			ticket.agent_instructions or ""
		]
		return "\n".join(parts)

	def _get_epic_body(self, epic: Any) -> str:
		parts = [
			epic.goal_text or "",
			epic.context_text or "",
			"\n".join(epic.success_metrics)
		]
		return "\n".join(parts)

	def _get_adr_body(self, adr: Any) -> str:
		parts = [
			adr.context_text or "",
			adr.decision_text or "",
			adr.consequences_text or "",
			adr.alternatives_text or ""
		]
		return "\n".join(parts)

	def update_entity(self, entity_type: str, entity_id: str) -> None:
		"""Incremental update for a single entity after mutation."""
		# For simplicity, we just rebuild the indexes for now as SQLite FTS5 doesn't easily support single-row updates without reading back.
		# Actually, we can DELETE and INSERT.
		# But we also need to update tags.json which is a bit harder to do incrementally without loading the whole thing.
		# Given the "fire-and-forget" and "can always be rebuilt" nature, maybe a partial rebuild or just full rebuild is fine for small repos.
		# But let's try to do it properly.
		
		# For now, let's just trigger a rebuild to ensure consistency. 
		# In a real system, we'd do incremental updates.
		try:
			self.rebuild()
		except Exception:
			# Fire-and-forget
			pass

	def search(
		self,
		query: str,
		entity_type: str | None = None,
		tags: list[str] = [],
		status: str | None = None,
		since: date | None = None,
		limit: int = 10,
	) -> SearchResults:
		db = self._get_db()
		
		# Construct query
		where_clauses = ["search_index MATCH ?"]
		params = [query]

		if entity_type:
			where_clauses.append("entity_type = ?")
			params.append(entity_type)
		
		if status:
			where_clauses.append("status = ?")
			params.append(status)
		
		if since:
			where_clauses.append("updated_at >= ?")
			params.append(since.isoformat())

		if tags:
			for t in tags:
				where_clauses.append("tags LIKE ?")
				params.append(f"%{normalize_tag(t)}%")

		sql = f"""
			SELECT *, bm25(search_index) as score, snippet(search_index, 3, '**', '**', '...', 40) as excerpt
			FROM search_index
			WHERE {" AND ".join(where_clauses)}
			ORDER BY score
			LIMIT ?
		"""
		params.append(limit)

		try:
			cursor = db.execute(sql, params)
			rows = cursor.fetchall()
		except sqlite3.OperationalError as e:
			raise KaryaIndexError(f"Search failed: {e}")
		finally:
			db.close()

		results = []
		for row in rows:
			# Normalize score to 0.0-1.0. bm25 returns negative values, smaller is better.
			# This is a bit tricky to normalize without knowing max/min.
			# For now, let's just use a placeholder or raw score.
			results.append(
				SearchResultItem(
					entity_type=row["entity_type"],
					id=row["entity_id"],
					title=row["title"],
					excerpt=row["excerpt"] or "",
					tags=(row["tags"] or "").split(),
					score=abs(row["score"]), # Using absolute for now
					status=row["status"]
				)
			)
		return SearchResults(query=query, total=len(results), results=results)

	def find_related(self, entity_id: str, limit: int = 5) -> SearchResults:
		"""Find entities related to entity_id by tag overlap."""
		if not self._tags_path.exists():
			return SearchResults(query=f"related:{entity_id}", total=0, results=[])

		with open(self._tags_path, "r", encoding="utf-8") as f:
			tags_index = json.load(f)

		# 1. Find tags for this entity
		target_tags = []
		for tag, entities in tags_index.items():
			if any(e["id"] == entity_id for e in entities):
				target_tags.append(tag)

		if not target_tags:
			return SearchResults(query=f"related:{entity_id}", total=0, results=[])

		# 2. Find all entities sharing at least one tag
		related_scores: Dict[str, Dict[str, Any]] = {}
		for tag in target_tags:
			for entry in tags_index.get(tag, []):
				eid = entry["id"]
				if eid == entity_id:
					continue
				
				if eid not in related_scores:
					related_scores[eid] = {"id": eid, "type": entry["type"], "score": 0, "tags": []}
				
				related_scores[eid]["score"] += 1
				related_scores[eid]["tags"].append(tag)

		# 3. Sort by score
		sorted_related = sorted(related_scores.values(), key=lambda x: x["score"], reverse=True)[:limit]

		# 4. Fetch details (title) from DB
		db = self._get_db()
		results = []
		for item in sorted_related:
			row = db.execute("SELECT title, excerpt FROM (SELECT *, snippet(search_index, 3, '**', '**', '...', 40) as excerpt FROM search_index) WHERE entity_id = ?", (item["id"],)).fetchone()
			results.append(
				SearchResultItem(
					entity_type=item["type"],
					id=item["id"],
					title=row["title"] if row else "Unknown",
					excerpt=row["excerpt"] if row else "",
					tags=item["tags"],
					score=float(item["score"] / len(target_tags)), # Normalized to 0.0-1.0
					status=None
				)
			)
		db.close()

		return SearchResults(query=f"related:{entity_id}", total=len(results), results=results)

	def get_tags(self, entity_id: str | None = None) -> dict:
		if not self._tags_path.exists():
			return {}

		with open(self._tags_path, "r", encoding="utf-8") as f:
			tags_index = json.load(f)

		if entity_id:
			entity_tags = []
			for tag, entities in tags_index.items():
				if any(e["id"] == entity_id for e in entities):
					entity_tags.append(tag)
			return {entity_id: entity_tags}
		else:
			cloud = {tag: len(entities) for tag, entities in tags_index.items()}
			return cloud
