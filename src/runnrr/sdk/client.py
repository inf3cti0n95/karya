"""Runnrr SDK Client."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from runnrr.core.filesystem import init_runnrr, normalize_root, find_runnrr_root
from runnrr.core.db import Database
from runnrr.core.models import ADR, Epic, Priority, Ticket, TicketStatus, TicketType, EpicType
from runnrr.exceptions import RunnrrNotInitializedError, TicketNotFoundError
from runnrr.services.adr_service import ADRService
from runnrr.services.epic_service import EpicService
from runnrr.services.ticket_service import TicketService
from runnrr.services.context_service import ContextService
from runnrr.services.search_service import SearchService
from runnrr.services.link_service import LinkService
from runnrr.services.action_service import ActionService


class RunnrrClient:
	def __init__(self, root: str | Path = ".", agent: str | None = None, db_path: str | Path | None = None):
		self.agent = agent
		self._db: Database | None = None
		
		try:
			if db_path:
				self.root = normalize_root(Path(root))
				self._db = Database(Path(db_path))
			else:
				self.root = find_runnrr_root(Path(root))
				from runnrr.core.filesystem import RUNNRR_ROOT
				self._db = Database(self.root / RUNNRR_ROOT / "runnrr.db")
				
			self._db.connect()
			self._db.migrate()

			self._tickets = TicketService(self._db)
			self._epics = EpicService(self._db)
			self._adrs = ADRService(self._db)
			self._context = ContextService(self._db)
			self._search = SearchService(self._db)
			self._links = LinkService(self._db)
			self._actions = ActionService(self._db)
		except RunnrrNotInitializedError:
			self.root = normalize_root(Path(root))
			# We leave self._db as None. Service methods will fail if they need it.

	def _ensure_init(self) -> None:
		if self._db is None:
			raise RunnrrNotInitializedError("No .runnrr/ directory found. Run `runnrr init` first.")

	def init(self) -> None:
		# Special case for init: it doesn't use find_runnrr_root because it's creating it
		# but it SHOULD fail if it's already in a parent tree.
		try:
			existing_root = find_runnrr_root(self.root)
			raise Exception(f"Runnrr already initialized at {existing_root}")
		except RunnrrNotInitializedError:
			pass
		
		init_runnrr(self.root)
		from runnrr.core.filesystem import RUNNRR_ROOT
		self._db = Database(self.root / RUNNRR_ROOT / "runnrr.db")
		self._db.connect()
		self._db.migrate()
		
		# Initialize services now that we have a DB
		self._tickets = TicketService(self._db)
		self._epics = EpicService(self._db)
		self._adrs = ADRService(self._db)
		self._context = ContextService(self._db)
		self._search = SearchService(self._db)
		self._links = LinkService(self._db)
		self._actions = ActionService(self._db)

	def close(self) -> None:
		"""Close the database connection."""
		if self._db:
			self._db.close()

	def migrate(self, force: bool = False) -> Dict[str, Any]:
		"""
		Migrate from v0.1.x markdown files to SQLite database.
		"""
		self._ensure_init()
		from runnrr.core.filesystem import list_tickets_in_state, list_all_epics, list_all_adrs, TICKET_DIRS, archive_v01
		from runnrr.core.parser import parse_ticket, parse_epic, parse_adr

		# Check if DB already has data
		row = self._db.execute("SELECT COUNT(*) as count FROM tickets").fetchone()
		if row['count'] > 0 and not force:
			raise Exception("Database already has data. Use --force to migrate anyway.")

		stats = {"tickets": 0, "epics": 0, "adrs": 0}

		# 1. Migrate Epics first (due to FK constraints)
		for path in list_all_epics(self.root):
			epic = parse_epic(path)
			# We need a custom insert or use the service with a modified create
			# For simplicity during migration, we'll use a helper or direct SQL
			self._insert_epic_migration(epic)
			stats["epics"] += 1

		# 2. Migrate Tickets
		for status in TICKET_DIRS.keys():
			for path in list_tickets_in_state(status, self.root):
				ticket = parse_ticket(path)
				self._insert_ticket_migration(ticket)
				stats["tickets"] += 1

		# 3. Migrate ADRs
		for path in list_all_adrs(self.root):
			adr = parse_adr(path)
			self._insert_adr_migration(adr)
			stats["adrs"] += 1

		# 4. Archive old files
		archive_path = archive_v01(self.root)
		
		# 5. Rebuild search index
		self.rebuild_index()

		return {
			"status": "success",
			"counts": stats,
			"archive": str(archive_path)
		}

	def _insert_ticket_migration(self, ticket: Ticket):
		self._ensure_init()
		now = datetime.now(timezone.utc).isoformat()
		with self._db.transaction() as conn:
			conn.execute(
				"""
				INSERT OR REPLACE INTO tickets (
					id, title, status, type, priority, epic_id, 
					estimated_effort, goal, notes, created_at, updated_at
				) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				""",
				(
					ticket.id, ticket.title, ticket.status.value, 
					ticket.type.value, ticket.priority.value, ticket.epic,
					ticket.estimated_effort, ticket.goal_text, ticket.notes_text,
					ticket.created_at.isoformat(), ticket.updated_at.isoformat()
				)
			)
			for tag in ticket.tags:
				conn.execute("INSERT OR REPLACE INTO tags (entity_type, entity_id, tag) VALUES (?, ?, ?)",
							 ("ticket", ticket.id, tag))
			
			for task in ticket.tasks:
				conn.execute("INSERT INTO tasks (ticket_id, text, done) VALUES (?, ?, ?)",
							 (ticket.id, task['text'], 1 if task['done'] else 0))
				
			for ac in ticket.acceptance_criteria:
				conn.execute("INSERT INTO acceptance_criteria (ticket_id, text, done) VALUES (?, ?, ?)",
							 (ticket.id, ac['text'], 1 if ac['done'] else 0))
				
			for entry in ticket.execution_log:
				conn.execute("INSERT INTO log_entries (entity_type, entity_id, message, created_at) VALUES (?, ?, ?, ?)",
							 ("ticket", ticket.id, entry['message'], entry['timestamp']))

	def _insert_epic_migration(self, epic: Epic):
		self._ensure_init()
		with self._db.transaction() as conn:
			conn.execute(
				"""
				INSERT OR REPLACE INTO epics (
					id, title, type, priority, goal, notes, success_metrics, created_at, updated_at
				) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
				""",
				(
					epic.id, epic.title, epic.type.value, epic.priority.value,
					epic.goal_text, epic.notes_text, "\n".join(epic.success_metrics),
					epic.created_at.isoformat(), epic.updated_at.isoformat()
				)
			)
			for tag in epic.tags:
				conn.execute("INSERT OR REPLACE INTO tags (entity_type, entity_id, tag) VALUES (?, ?, ?)",
							 ("epic", epic.id, tag))

	def _insert_adr_migration(self, adr: ADR):
		self._ensure_init()
		now = datetime.now(timezone.utc).isoformat()
		with self._db.transaction() as conn:
			conn.execute(
				"""
				INSERT OR REPLACE INTO adrs (
					id, title, status, decision_date, context_text, decision_text,
					consequences, alternatives, created_at, updated_at
				) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				""",
				(
					adr.id, adr.title, adr.status.value, adr.date.isoformat(),
					adr.context_text, adr.decision_text, adr.consequences_text,
					adr.alternatives_text, now, now
				)
			)
			for tag in adr.tags:
				conn.execute("INSERT OR REPLACE INTO tags (entity_type, entity_id, tag) VALUES (?, ?, ?)",
							 ("adr", adr.id, tag))
			
			for t_id in adr.linked_tickets:
				conn.execute("INSERT OR REPLACE INTO links (source_type, source_id, target_type, target_id) VALUES (?, ?, ?, ?)",
							 ("adr", adr.id, "ticket", t_id))
				conn.execute("INSERT OR REPLACE INTO links (source_type, source_id, target_type, target_id) VALUES (?, ?, ?, ?)",
							 ("ticket", t_id, "adr", adr.id))
			
			for e_id in adr.linked_epics:
				conn.execute("INSERT OR REPLACE INTO links (source_type, source_id, target_type, target_id) VALUES (?, ?, ?, ?)",
							 ("adr", adr.id, "epic", e_id))
				conn.execute("INSERT OR REPLACE INTO links (source_type, source_id, target_type, target_id) VALUES (?, ?, ?, ?)",
							 ("epic", e_id, "adr", adr.id))

	def list_events(
		self,
		ticket: str | None = None,
		epic: str | None = None,
		adr: str | None = None,
		since: str | None = None,
		limit: int = 20,
	) -> list[dict]:
		"""List events from the audit trail."""
		self._ensure_init()
		query = "SELECT * FROM events WHERE 1=1"
		params = []
		
		if ticket:
			query += " AND entity_type = 'ticket' AND entity_id = ?"
			params.append(ticket)
		if epic:
			query += " AND entity_type = 'epic' AND entity_id = ?"
			params.append(epic)
		if adr:
			query += " AND entity_type = 'adr' AND entity_id = ?"
			params.append(adr)
		if since:
			query += " AND created_at >= ?"
			params.append(since)
			
		query += " ORDER BY created_at DESC LIMIT ?"
		params.append(limit)
		
		rows = self._db.execute(query, tuple(params)).fetchall()
		events = []
		for row in rows:
			d = dict(row)
			d['data'] = json.loads(d['data'])
			events.append(d)
		return events

	def export_entity(self, entity_id: str, out_file: str | None = None) -> str:
		"""Export a single entity as markdown."""
		self._ensure_init()
		from runnrr.core.filesystem import export_ticket_md, export_epic_md, export_adr_md
		
		if entity_id.startswith("TICKET-"):
			entity = self.get_ticket(entity_id)
			content = export_ticket_md(entity)
		elif entity_id.startswith("EPIC-"):
			entity = self.get_epic(entity_id)
			content = export_epic_md(entity)
		elif entity_id.startswith("ADR-"):
			entity = self.get_adr(entity_id)
			content = export_adr_md(entity)
		else:
			raise ValueError(f"Unknown entity type: {entity_id}")
			
		if out_file:
			out_path = Path(out_file)
			out_path.parent.mkdir(parents=True, exist_ok=True)
			out_path.write_text(content, encoding="utf-8")
			
		return content

	def export_all(self, out_dir: str | None = None) -> Dict[str, Any]:
		"""Export all entities as markdown files."""
		self._ensure_init()
		if not out_dir:
			out_dir = str(self.root / "export")
			
		out_path = Path(out_dir)
		out_path.mkdir(parents=True, exist_ok=True)
		
		counts = {"tickets": 0, "epics": 0, "adrs": 0}
		
		# Tickets
		tickets = self.list_tickets()
		for t in tickets:
			self.export_entity(t.id, out_file=str(out_path / "tickets" / f"{t.id}.md"))
			counts["tickets"] += 1
			
		# Epics
		epics = self.list_epics()
		for e in epics:
			self.export_entity(e.id, out_file=str(out_path / "epics" / f"{e.id}.md"))
			counts["epics"] += 1
			
		# ADRs
		adrs = self.list_adrs()
		for a in adrs:
			self.export_entity(a.id, out_file=str(out_path / "adrs" / f"{a.id}.md"))
			counts["adrs"] += 1
			
		return {
			"status": "success",
			"counts": counts,
			"path": str(out_path)
		}

	def next_ticket_id(self) -> str:
		self._ensure_init()
		row = self._db.execute("SELECT MAX(CAST(SUBSTR(id, 8) AS INTEGER)) as max_id FROM tickets").fetchone()
		max_id = row['max_id'] or 0
		return f"TICKET-{(max_id + 1):03d}"

	def next_epic_id(self) -> str:
		self._ensure_init()
		row = self._db.execute("SELECT MAX(CAST(SUBSTR(id, 6) AS INTEGER)) as max_id FROM epics").fetchone()
		max_id = row['max_id'] or 0
		return f"EPIC-{(max_id + 1):03d}"

	def next_adr_id(self) -> str:
		self._ensure_init()
		row = self._db.execute("SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) as max_id FROM adrs").fetchone()
		max_id = row['max_id'] or 0
		return f"ADR-{(max_id + 1):03d}"

	def get_summary(self) -> Dict[str, int]:
		"""Get summary counts of tickets by status."""
		self._ensure_init()
		rows = self._db.execute("SELECT status, COUNT(*) as count FROM tickets GROUP BY status").fetchall()
		counts = {s.value: 0 for s in TicketStatus}
		for row in rows:
			counts[row['status']] = row['count']
		return counts

	def get_status_info(self) -> Dict[str, Any]:
		"""Get detailed status and health info for the workspace."""
		self._ensure_init()
		import os
		from runnrr.core.filesystem import RUNNRR_ROOT, find_host_gitignore
		
		db_size = os.path.getsize(self._db.db_path) if self._db.db_path.exists() else 0
		schema_version = self._db.execute("PRAGMA user_version").fetchone()[0]
		
		ticket_summary = self.get_summary()
		epic_count = self._db.execute("SELECT COUNT(*) FROM epics").fetchone()[0]
		adr_count = self._db.execute("SELECT COUNT(*) FROM adrs").fetchone()[0]
		
		host_gitignore = find_host_gitignore(self.root)
		git_isolated = False
		if host_gitignore and host_gitignore.exists():
			content = host_gitignore.read_text(encoding="utf-8")
			if f"{RUNNRR_ROOT}/" in content:
				git_isolated = True
				
		return {
			"project_root": str(self.root),
			"database": {
				"path": str(self._db.db_path),
				"size_kb": round(db_size / 1024, 2),
				"schema_version": schema_version,
				"healthy": True
			},
			"counts": {
				"tickets": ticket_summary,
				"epics": epic_count,
				"adrs": adr_count
			},
			"git_isolated": git_isolated,
			"host_gitignore": str(host_gitignore) if host_gitignore else None
		}

	# Tickets
	def get_next_ticket(self, tag: str | None = None, epic: str | None = None) -> Ticket | None:
		self._ensure_init()
		return self._tickets.get_next(tag=tag, epic=epic)

	def build_context(self, ticket_id: str, budget: int = 4000) -> Dict[str, Any]:
		self._ensure_init()
		return self._context.build_context(ticket_id, budget=budget)
		
	# Actions (Agent Interface)
	def valid_actions(self, ticket_id: str) -> List[Dict[str, Any]]:
		self._ensure_init()
		return self._actions.valid_actions(ticket_id)
		
	def execute(self, ticket_id: str | None = None) -> Dict[str, Any]:
		self._ensure_init()
		return self._actions.exec(ticket_id)

	# Search & Links
	def rebuild_index(self) -> None:
		self._ensure_init()
		self._search.rebuild_index()
		
	def search(self, query: str) -> List[Dict[str, Any]]:
		self._ensure_init()
		return self._search.search(query)
		
	def find_related(self, entity_id: str) -> List[Dict[str, Any]]:
		self._ensure_init()
		return self._search.find_related(entity_id)
		
	def link(self, source_id: str, target_id: str) -> None:
		self._ensure_init()
		self._links.link(source_id, target_id, actor=self.agent)

	def create_ticket(
		self,
		title: str,
		goal: str = "",
		type: TicketType = TicketType.FEATURE,
		priority: Priority = Priority.MEDIUM,
		epic: str | None = None,
		tags: list[str] | None = None,
		estimated_effort: int = 1,
	) -> Ticket:
		self._ensure_init()
		return self._tickets.create(
			title=title,
			goal=goal,
			type=type,
			priority=priority,
			epic=epic,
			tags=tags,
			estimated_effort=estimated_effort,
			actor=self.agent,
		)

	def get_ticket(self, ticket_id: str) -> Ticket:
		self._ensure_init()
		return self._tickets.get(ticket_id)

	def list_tickets(
		self,
		status: str | list[str] | None = None,
		owner: str | None = None,
		epic: str | None = None,
		tag: str | None = None,
	) -> list[Ticket]:
		self._ensure_init()
		return self._tickets.list(status=status, owner=owner, epic=epic, tag=tag)

	def transition(self, ticket_id: str, new_status: str) -> Ticket:
		self._ensure_init()
		return self._tickets.transition(ticket_id, new_status, actor=self.agent)

	def update_ticket(self, ticket_id: str, updates: dict) -> Ticket:
		self._ensure_init()
		return self._tickets.update(ticket_id, updates, actor=self.agent)

	def log(self, ticket_id: str, message: str) -> Ticket:
		self._ensure_init()
		return self._tickets.log(ticket_id, message, actor=self.agent)

	def add_ticket_task(self, ticket_id: str, text: str) -> Ticket:
		self._ensure_init()
		return self._tickets.add_task(ticket_id, text)

	def check_ticket_task(self, ticket_id: str, index: int) -> Ticket:
		self._ensure_init()
		return self._tickets.update_task_status(ticket_id, index, done=True)

	def uncheck_ticket_task(self, ticket_id: str, index: int) -> Ticket:
		self._ensure_init()
		return self._tickets.update_task_status(ticket_id, index, done=False)

	def add_ticket_ac(self, ticket_id: str, text: str) -> Ticket:
		self._ensure_init()
		return self._tickets.add_acceptance_criteria(ticket_id, text)

	def check_ticket_ac(self, ticket_id: str, index: int) -> Ticket:
		self._ensure_init()
		return self._tickets.update_ac_status(ticket_id, index, done=True)

	def uncheck_ticket_ac(self, ticket_id: str, index: int) -> Ticket:
		self._ensure_init()
		return self._tickets.update_ac_status(ticket_id, index, done=False)

	def block(self, ticket_id: str, reason: str) -> Ticket:
		self._ensure_init()
		return self._tickets.block(ticket_id, reason, actor=self.agent)

	def describe_ticket(self, ticket_id: str) -> dict:
		self._ensure_init()
		return self._tickets.describe(ticket_id)

	# Epics
	def create_epic(
		self,
		title: str,
		goal: str = "",
		type: EpicType = EpicType.FEATURE,
		priority: Priority = Priority.MEDIUM,
		tags: list[str] | None = None,
	) -> Epic:
		self._ensure_init()
		return self._epics.create(
			title=title,
			goal=goal,
			type=type,
			priority=priority,
			tags=tags,
			actor=self.agent,
		)

	def get_epic(self, epic_id: str) -> Epic:
		self._ensure_init()
		return self._epics.get(epic_id)

	def list_epics(self, tag: str | None = None) -> list[Epic]:
		self._ensure_init()
		return self._epics.list(tag=tag)

	def describe_epic(self, epic_id: str) -> dict:
		self._ensure_init()
		return self._epics.describe(epic_id)

	def update_epic(self, epic_id: str, updates: dict) -> Epic:
		self._ensure_init()
		return self._epics.update(epic_id, updates, actor=self.agent)

	# ADRs
	def create_adr(
		self,
		title: str,
		context: str,
		decision: str,
		consequences: str = "",
		alternatives: str = "",
		linked_tickets: list[str] | None = None,
		linked_epics: list[str] | None = None,
		tags: list[str] | None = None,
	) -> ADR:
		self._ensure_init()
		return self._adrs.create(
			title=title,
			context=context,
			decision=decision,
			consequences=consequences,
			alternatives=alternatives,
			linked_tickets=linked_tickets,
			linked_epics=linked_epics,
			tags=tags,
			actor=self.agent,
		)

	def get_adr(self, adr_id: str) -> ADR:
		self._ensure_init()
		return self._adrs.get(adr_id)

	def list_adrs(self, status: str | None = None, tag: str | None = None) -> list[ADR]:
		self._ensure_init()
		return self._adrs.list(status=status, tag=tag)

	def accept_adr(self, adr_id: str) -> ADR:
		self._ensure_init()
		return self._adrs.accept(adr_id, actor=self.agent)

	def describe_adr(self, adr_id: str) -> dict:
		self._ensure_init()
		return self._adrs.describe(adr_id)

	def update_adr(self, adr_id: str, updates: dict) -> ADR:
		self._ensure_init()
		return self._adrs.update(adr_id, updates, actor=self.agent)
