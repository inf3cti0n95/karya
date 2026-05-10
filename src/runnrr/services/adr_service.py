"""ADR service operations using SQLite."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from runnrr.core.db import Database, emit_event, next_adr_id
from runnrr.core.models import ADR, ADRStatus, normalize_tag

class ADRService:
    def __init__(self, db: Database):
        self.db = db

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
        adr_id = next_adr_id(self.db)
        now = datetime.now(timezone.utc).isoformat()
        today = date.today().isoformat()
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

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO adrs (
                    id, title, status, decision_date, context_text, decision_text,
                    consequences, alternatives, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    adr.id, adr.title, adr.status.value, today,
                    adr.context_text, adr.decision_text, adr.consequences_text,
                    adr.alternatives_text, now, now
                )
            )
            
            for tag in normalized_tags:
                conn.execute(
                    "INSERT INTO tags (entity_type, entity_id, tag) VALUES (?, ?, ?)",
                    ("adr", adr.id, tag)
                )
            
            # Bidirectional links
            for t_id in (linked_tickets or []):
                conn.execute(
                    "INSERT INTO links (source_type, source_id, target_type, target_id) VALUES (?, ?, ?, ?)",
                    ("adr", adr.id, "ticket", t_id)
                )
                conn.execute(
                    "INSERT INTO links (source_type, source_id, target_type, target_id) VALUES (?, ?, ?, ?)",
                    ("ticket", t_id, "adr", adr.id)
                )
            
            for e_id in (linked_epics or []):
                conn.execute(
                    "INSERT INTO links (source_type, source_id, target_type, target_id) VALUES (?, ?, ?, ?)",
                    ("adr", adr.id, "epic", e_id)
                )
                conn.execute(
                    "INSERT INTO links (source_type, source_id, target_type, target_id) VALUES (?, ?, ?, ?)",
                    ("epic", e_id, "adr", adr.id)
                )
            
            # Index for search
            body = f"{adr.context_text or ''} {adr.decision_text or ''} {adr.consequences_text or ''} {adr.alternatives_text or ''}"
            conn.execute(
                "INSERT INTO search_index (entity_type, entity_id, title, body, tags) VALUES (?, ?, ?, ?, ?)",
                ("adr", adr.id, adr.title, body, " ".join(normalized_tags))
            )

        emit_event(self.db, "adr.created", "adr", adr.id, actor)
        return adr

    def get(self, adr_id: str) -> ADR:
        row = self.db.execute("SELECT * FROM adrs WHERE id = ?", (adr_id,)).fetchone()
        if not row:
            raise Exception(f"ADR '{adr_id}' not found.")
        return self._map_row_to_adr(row)

    def list(
        self,
        status: str | None = None,
        tag: str | None = None,
    ) -> list[ADR]:
        query = "SELECT * FROM adrs WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        if tag:
            query += " AND id IN (SELECT entity_id FROM tags WHERE entity_type = 'adr' AND tag = ?)"
            params.append(normalize_tag(tag))
            
        rows = self.db.execute(query, tuple(params)).fetchall()
        return [self._map_row_to_adr(row) for row in rows]

    def update(self, adr_id: str, updates: dict, actor: str | None = None) -> ADR:
        allowed_fields = {
            "title", "status", "decision_date", "context_text", 
            "decision_text", "consequences", "alternatives",
            "supersedes", "superseded_by"
        }
        
        query_parts = []
        params = []
        for field, value in updates.items():
            if field in allowed_fields:
                query_parts.append(f"{field} = ?")
                params.append(value)
            elif field == "tags":
                self._update_tags(adr_id, value)

        if query_parts:
            now = datetime.now(timezone.utc).isoformat()
            query_parts.append("updated_at = ?")
            params.append(now)
            
            query = f"UPDATE adrs SET {', '.join(query_parts)} WHERE id = ?"
            params.append(adr_id)
            
            with self.db.transaction() as conn:
                conn.execute(query, tuple(params))
                # Update search index
                adr = self.get(adr_id)
                body = f"{adr.context_text or ''} {adr.decision_text or ''} {adr.consequences_text or ''} {adr.alternatives_text or ''}"
                conn.execute(
                    "UPDATE search_index SET title = ?, body = ?, tags = ? WHERE entity_id = ?",
                    (adr.title, body, " ".join(adr.tags), adr_id)
                )

        emit_event(self.db, "adr.updated", "adr", adr_id, actor, data=updates)
        return self.get(adr_id)

    def accept(self, adr_id: str, actor: str | None = None) -> ADR:
        adr = self.get(adr_id)
        if adr.status != ADRStatus.PROPOSED:
            raise Exception(f"Cannot accept ADR in status {adr.status}")
        
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE adrs SET status = ?, updated_at = ? WHERE id = ?",
                (ADRStatus.ACCEPTED.value, now, adr_id)
            )
            
        emit_event(self.db, "adr.accepted", "adr", adr_id, actor)
        return self.get(adr_id)

    def describe(self, adr_id: str) -> dict:
        adr = self.get(adr_id)
        return adr.model_dump(mode="json")

    def _map_row_to_adr(self, row: sqlite3.Row) -> ADR:
        data = dict(row)
        adr_id = data['id']
        
        # Load tags
        tag_rows = self.db.execute(
            "SELECT tag FROM tags WHERE entity_type = 'adr' AND entity_id = ?",
            (adr_id,)
        ).fetchall()
        data['tags'] = [r['tag'] for r in tag_rows]
        
        # Load linked tickets
        ticket_rows = self.db.execute(
            "SELECT target_id FROM links WHERE source_type = 'adr' AND source_id = ? AND target_type = 'ticket'",
            (adr_id,)
        ).fetchall()
        data['linked_tickets'] = [r['target_id'] for r in ticket_rows]
        
        # Load linked epics
        epic_rows = self.db.execute(
            "SELECT target_id FROM links WHERE source_type = 'adr' AND source_id = ? AND target_type = 'epic'",
            (adr_id,)
        ).fetchall()
        data['linked_epics'] = [r['target_id'] for r in epic_rows]
        
        # Map fields
        data['date'] = date.fromisoformat(data.pop('decision_date'))
        data['consequences_text'] = data.pop('consequences')
        data['alternatives_text'] = data.pop('alternatives')
        
        # Convert strings to types
        data['status'] = ADRStatus(data['status'])
        
        return ADR(**data)

    def _update_tags(self, adr_id: str, tags: list[str]):
        normalized_tags = [normalize_tag(t) for t in tags]
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM tags WHERE entity_type = 'adr' AND entity_id = ?", (adr_id,))
            for tag in normalized_tags:
                conn.execute(
                    "INSERT INTO tags (entity_type, entity_id, tag) VALUES (?, ?, ?)",
                    ("adr", adr_id, tag)
                )
