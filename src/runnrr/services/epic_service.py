"""Epic service operations using SQLite."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from runnrr.core.db import Database, emit_event, next_epic_id
from runnrr.core.models import Epic, EpicStatus, EpicType, Priority, normalize_tag
from runnrr.exceptions import ValidationError

class EpicService:
    def __init__(self, db: Database):
        self.db = db

    def create(
        self,
        title: str,
        goal: str = "",
        type: EpicType = EpicType.FEATURE,
        priority: Priority = Priority.MEDIUM,
        tags: list[str] | None = None,
        actor: str | None = None,
    ) -> Epic:
        epic_id = next_epic_id(self.db)
        now = datetime.now(timezone.utc).isoformat()
        normalized_tags = [normalize_tag(t) for t in (tags or [])]
        
        epic = Epic(
            id=epic_id,
            title=title,
            type=type,
            priority=priority,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
            tags=normalized_tags,
            goal_text=goal,
        )

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO epics (
                    id, title, type, priority, goal, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    epic.id, epic.title, epic.type.value, epic.priority.value,
                    epic.goal_text, now, now
                )
            )
            
            for tag in normalized_tags:
                conn.execute(
                    "INSERT INTO tags (entity_type, entity_id, tag) VALUES (?, ?, ?)",
                    ("epic", epic.id, tag)
                )
            
            # Index for search
            conn.execute(
                "INSERT INTO search_index (entity_type, entity_id, title, body, tags) VALUES (?, ?, ?, ?, ?)",
                ("epic", epic.id, epic.title, epic.goal_text or "", " ".join(normalized_tags))
            )

        emit_event(self.db, "epic.created", "epic", epic.id, actor)
        return epic

    def get(self, epic_id: str) -> Epic:
        row = self.db.execute("SELECT * FROM epics WHERE id = ?", (epic_id,)).fetchone()
        if not row:
            raise Exception(f"Epic '{epic_id}' not found.")
        return self._map_row_to_epic(row)

    def list(
        self,
        tag: str | None = None,
    ) -> list[Epic]:
        query = "SELECT * FROM epics WHERE 1=1"
        params = []
        
        if tag:
            query += " AND id IN (SELECT entity_id FROM tags WHERE entity_type = 'epic' AND tag = ?)"
            params.append(normalize_tag(tag))
            
        rows = self.db.execute(query, tuple(params)).fetchall()
        return [self._map_row_to_epic(row) for row in rows]

    def update(self, epic_id: str, updates: dict, actor: str | None = None) -> Epic:
        allowed_fields = {"title", "type", "priority", "owner", "goal", "notes", "success_metrics"}
        
        query_parts = []
        params = []
        for field, value in updates.items():
            if field in allowed_fields:
                if field == "success_metrics" and isinstance(value, list):
                    value = "\n".join(value)
                query_parts.append(f"{field} = ?")
                params.append(value)
            elif field == "tags":
                self._update_tags(epic_id, value)

        if query_parts:
            now = datetime.now(timezone.utc).isoformat()
            query_parts.append("updated_at = ?")
            params.append(now)
            
            query = f"UPDATE epics SET {', '.join(query_parts)} WHERE id = ?"
            params.append(epic_id)
            
            with self.db.transaction() as conn:
                conn.execute(query, tuple(params))
                # Update search index
                epic = self.get(epic_id)
                conn.execute(
                    "UPDATE search_index SET title = ?, body = ?, tags = ? WHERE entity_id = ?",
                    (epic.title, (epic.goal_text or "") + " " + (epic.notes_text or ""), 
                     " ".join(epic.tags), epic_id)
                )

        emit_event(self.db, "epic.updated", "epic", epic_id, actor, data=updates)
        return self.get(epic_id)

    def describe(self, epic_id: str) -> dict:
        epic = self.get(epic_id)
        data = epic.model_dump(mode="json")
        
        # Compute status and progress from tickets
        tickets = self._get_epic_tickets(epic_id)
        if not tickets:
            data["status"] = "planned"
            data["progress"] = {"done": 0, "total": 0, "percent": 0}
        else:
            done = [t for t in tickets if t['status'] == "done"]
            total = len(tickets)
            percent = int((len(done) / total) * 100) if total > 0 else 0
            data["progress"] = {"done": len(done), "total": total, "percent": percent}
            
            if all(t['status'] == "done" for t in tickets):
                data["status"] = "done"
            elif any(t['status'] in ["in-progress", "done"] for t in tickets):
                data["status"] = "active"
            else:
                data["status"] = "planned"
        
        return data

    def _get_epic_tickets(self, epic_id: str) -> List[Dict[str, Any]]:
        rows = self.db.execute("SELECT id, status FROM tickets WHERE epic_id = ?", (epic_id,)).fetchall()
        return [dict(r) for r in rows]

    def _map_row_to_epic(self, row: sqlite3.Row) -> Epic:
        data = dict(row)
        epic_id = data['id']
        
        # Load tags
        tag_rows = self.db.execute(
            "SELECT tag FROM tags WHERE entity_type = 'epic' AND entity_id = ?",
            (epic_id,)
        ).fetchall()
        data['tags'] = [r['tag'] for r in tag_rows]
        
        # Load linked ADRs
        link_rows = self.db.execute(
            "SELECT target_id FROM links WHERE source_type = 'epic' AND source_id = ? AND target_type = 'adr'",
            (epic_id,)
        ).fetchall()
        data['linked_adrs'] = [r['target_id'] for r in link_rows]
        
        # Load linked tickets
        ticket_rows = self.db.execute(
            "SELECT id FROM tickets WHERE epic_id = ?",
            (epic_id,)
        ).fetchall()
        # The Epic model might not have a linked_tickets field, but it's useful for describe
        
        # Map fields
        data['goal_text'] = data.pop('goal')
        data['notes_text'] = data.pop('notes')
        
        metrics = data.pop('success_metrics')
        data['success_metrics'] = metrics.split("\n") if metrics else []
        
        # Convert strings to types
        data['type'] = EpicType(data['type'])
        data['priority'] = Priority(data['priority'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        
        return Epic(**data)

    def _update_tags(self, epic_id: str, tags: list[str]):
        normalized_tags = [normalize_tag(t) for t in tags]
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM tags WHERE entity_type = 'epic' AND entity_id = ?", (epic_id,))
            for tag in normalized_tags:
                conn.execute(
                    "INSERT INTO tags (entity_type, entity_id, tag) VALUES (?, ?, ?)",
                    ("epic", epic_id, tag)
                )
