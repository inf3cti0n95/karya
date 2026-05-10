import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_VERSION = 1

INITIAL_SCHEMA = """
-- Core entities
CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'backlog',
    type TEXT NOT NULL DEFAULT 'feature',
    priority TEXT NOT NULL DEFAULT 'medium',
    epic_id TEXT REFERENCES epics(id),
    owner TEXT,
    estimated_effort INTEGER DEFAULT 1,
    goal TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS epics (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'feature',
    priority TEXT NOT NULL DEFAULT 'medium',
    owner TEXT,
    goal TEXT,
    success_metrics TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS adrs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',
    decision_date TEXT NOT NULL,
    context_text TEXT,
    decision_text TEXT,
    consequences TEXT,
    alternatives TEXT,
    supersedes TEXT REFERENCES adrs(id),
    superseded_by TEXT REFERENCES adrs(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tags (
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (entity_type, entity_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS acceptance_criteria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS log_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    message TEXT NOT NULL,
    actor TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dependencies (
    ticket_id TEXT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    blocked_by TEXT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    PRIMARY KEY (ticket_id, blocked_by)
);

CREATE TABLE IF NOT EXISTS links (
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    PRIMARY KEY (source_type, source_id, target_type, target_id)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    actor TEXT,
    data TEXT,
    created_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    entity_type,
    entity_id,
    title,
    body,
    tags
);
"""

class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """Open connection. Enable WAL mode for concurrent reads."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

    def migrate(self) -> None:
        """
        Run schema migrations. Check user_version pragma.
        If 0, run initial schema.
        """
        if not self._conn:
            self.connect()
            
        current = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if current < 1:
            self._run_initial_schema()
            self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self._conn.commit()

    def _run_initial_schema(self) -> None:
        self._conn.executescript(INITIAL_SCHEMA)

    @contextmanager
    def transaction(self):
        """Context manager for explicit transactions."""
        if not self._conn:
            self.connect()
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        if not self._conn:
            self.connect()
        return self._conn.execute(sql, params)

    def executescript(self, sql: str) -> sqlite3.Cursor:
        if not self._conn:
            self.connect()
        return self._conn.executescript(sql)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

def emit_event(db: Database, event_type: str, entity_type: str, entity_id: str, actor: Optional[str], data: dict = {}) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO events (event_type, entity_type, entity_id, actor, data, created_at) VALUES (?,?,?,?,?,?)",
            (event_type, entity_type, entity_id, actor, json.dumps(data), now)
        )


def next_ticket_id(db: Database) -> str:
    row = db.execute("SELECT MAX(CAST(SUBSTR(id, 8) AS INTEGER)) as max_id FROM tickets").fetchone()
    max_id = row['max_id'] or 0
    return f"TICKET-{(max_id + 1):03d}"


def next_epic_id(db: Database) -> str:
    row = db.execute("SELECT MAX(CAST(SUBSTR(id, 6) AS INTEGER)) as max_id FROM epics").fetchone()
    max_id = row['max_id'] or 0
    return f"EPIC-{(max_id + 1):03d}"


def next_adr_id(db: Database) -> str:
    row = db.execute("SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) as max_id FROM adrs").fetchone()
    max_id = row['max_id'] or 0
    return f"ADR-{(max_id + 1):03d}"
