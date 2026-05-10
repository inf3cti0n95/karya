"""Ticket service operations using SQLite."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from runnrr.core.db import Database, emit_event, next_ticket_id
from runnrr.core.models import Priority, Ticket, TicketStatus, TicketType, normalize_tag
from runnrr.core.state import validate_transition
from runnrr.exceptions import (
    IncompleteAcceptanceCriteria,
    TicketNotFoundError,
    ValidationError,
)

class TicketService:
    def __init__(self, db: Database):
        self.db = db

    def create(
        self,
        title: str,
        goal: str = "",
        type: TicketType = TicketType.FEATURE,
        priority: Priority = Priority.MEDIUM,
        epic: str | None = None,
        tags: list[str] | None = None,
        estimated_effort: int = 1,
        actor: str | None = None,
    ) -> Ticket:
        # Generate ID
        ticket_id = next_ticket_id(self.db)
        now = datetime.now(timezone.utc).isoformat()
        
        normalized_tags = [normalize_tag(t) for t in (tags or [])]
        
        ticket = Ticket(
            id=ticket_id,
            title=title,
            status=TicketStatus.BACKLOG,
            type=type,
            priority=priority,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
            epic=epic,
            tags=normalized_tags,
            estimated_effort=estimated_effort,
            goal_text=goal,
        )

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO tickets (
                    id, title, status, type, priority, epic_id, 
                    estimated_effort, goal, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket.id, ticket.title, ticket.status.value, 
                    ticket.type.value, ticket.priority.value, ticket.epic,
                    ticket.estimated_effort, ticket.goal_text, now, now
                )
            )
            
            for tag in normalized_tags:
                conn.execute(
                    "INSERT INTO tags (entity_type, entity_id, tag) VALUES (?, ?, ?)",
                    ("ticket", ticket.id, tag)
                )
            
            # Index for search
            conn.execute(
                "INSERT INTO search_index (entity_type, entity_id, title, body, tags) VALUES (?, ?, ?, ?, ?)",
                ("ticket", ticket.id, ticket.title, ticket.goal_text or "", " ".join(normalized_tags))
            )

        emit_event(self.db, "ticket.created", "ticket", ticket.id, actor)
        return ticket

    def get(self, ticket_id: str) -> Ticket:
        row = self.db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if not row:
            raise TicketNotFoundError(f"Ticket '{ticket_id}' not found.")
        
        return self._map_row_to_ticket(row)

    def list(
        self,
        status: str | list[str] | None = None,
        owner: str | None = None,
        epic: str | None = None,
        tag: str | None = None,
    ) -> list[Ticket]:
        query = "SELECT * FROM tickets WHERE 1=1"
        params = []
        
        if status:
            if isinstance(status, str):
                if status == "actionable":
                    query += " AND status IN ('todo', 'in-progress')"
                elif status != "all":
                    query += " AND status = ?"
                    params.append(status)
            elif isinstance(status, list):
                placeholders = ','.join(['?'] * len(status))
                query += f" AND status IN ({placeholders})"
                params.extend(status)
        else:
            # Default: actionable
            query += " AND status IN ('todo', 'in-progress')"
            
        if owner:
            query += " AND owner = ?"
            params.append(owner)
        if epic:
            query += " AND epic_id = ?"
            params.append(epic)
        if tag:
            query += " AND id IN (SELECT entity_id FROM tags WHERE entity_type = 'ticket' AND tag = ?)"
            params.append(normalize_tag(tag))
            
        # Default sorting: in-progress first, then priority, then effort, then created_at
        query += """
            ORDER BY 
                CASE status WHEN 'in-progress' THEN 1 WHEN 'todo' THEN 2 ELSE 3 END,
                CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'low' THEN 4 ELSE 5 END,
                estimated_effort ASC,
                created_at ASC
        """
            
        rows = self.db.execute(query, tuple(params)).fetchall()
        return [self._map_row_to_ticket(row) for row in rows]

    def transition(self, ticket_id: str, new_status: str, actor: str | None = None) -> Ticket:
        ticket = self.get(ticket_id)
        current_status = ticket.status.value

        validate_transition(current_status, new_status)

        if new_status == TicketStatus.DONE.value:
            # Refresh ticket with tasks/criteria
            ticket = self.get(ticket_id)
            unchecked = [i["text"] for i in ticket.acceptance_criteria if not i.get("done")]
            if unchecked:
                raise IncompleteAcceptanceCriteria(unchecked)

        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE tickets SET status = ?, updated_at = ? WHERE id = ?",
                (new_status, now, ticket_id)
            )
            
        emit_event(self.db, "ticket.transitioned", "ticket", ticket_id, actor, 
                   data={"from": current_status, "to": new_status})
        return self.get(ticket_id)

    def update(self, ticket_id: str, updates: dict, actor: str | None = None) -> Ticket:
        # Validate fields
        allowed_fields = {
            "title", "type", "priority", "epic_id", "owner", 
            "estimated_effort", "goal", "notes"
        }
        
        query_parts = []
        params = []
        for field, value in updates.items():
            if field in allowed_fields:
                query_parts.append(f"{field} = ?")
                params.append(value)
            elif field == "tags":
                # Special handling for tags
                self._update_tags(ticket_id, value)
            elif field == "epic":
                # Support 'epic' alias for 'epic_id'
                query_parts.append("epic_id = ?")
                params.append(value)

        if query_parts:
            now = datetime.now(timezone.utc).isoformat()
            query_parts.append("updated_at = ?")
            params.append(now)
            
            query = f"UPDATE tickets SET {', '.join(query_parts)} WHERE id = ?"
            params.append(ticket_id)
            
            with self.db.transaction() as conn:
                conn.execute(query, tuple(params))
                # Update search index
                ticket = self.get(ticket_id)
                conn.execute(
                    "UPDATE search_index SET title = ?, body = ?, tags = ? WHERE entity_id = ?",
                    (ticket.title, (ticket.goal_text or "") + " " + (ticket.notes_text or ""), 
                     " ".join(ticket.tags), ticket_id)
                )

        emit_event(self.db, "ticket.updated", "ticket", ticket_id, actor, data=updates)
        return self.get(ticket_id)

    def log(self, ticket_id: str, message: str, actor: str | None = None) -> Ticket:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO log_entries (entity_type, entity_id, message, actor, created_at) VALUES (?, ?, ?, ?, ?)",
                ("ticket", ticket_id, message, actor, now)
            )
        
        emit_event(self.db, "ticket.logged", "ticket", ticket_id, actor, data={"message": message})
        return self.get(ticket_id)

    def add_task(self, ticket_id: str, text: str) -> Ticket:
        with self.db.transaction() as conn:
            # Get current max position
            row = conn.execute(
                "SELECT MAX(position) as max_pos FROM tasks WHERE ticket_id = ?",
                (ticket_id,)
            ).fetchone()
            next_pos = (row['max_pos'] or 0) + 1
            
            conn.execute(
                "INSERT INTO tasks (ticket_id, text, done, position) VALUES (?, ?, ?, ?)",
                (ticket_id, text, 0, next_pos)
            )
        emit_event(self.db, "ticket.updated", "ticket", ticket_id, actor=None, data={"add_task": text})
        return self.get(ticket_id)

    def update_task_status(self, ticket_id: str, index: int, done: bool) -> Ticket:
        # We use 0-based index matching the display order (position)
        tasks = self.db.execute(
            "SELECT id FROM tasks WHERE ticket_id = ? ORDER BY position",
            (ticket_id,)
        ).fetchall()
        
        if index < 0 or index >= len(tasks):
            raise ValidationError(f"Task index {index} out of range (0-{len(tasks)-1})")
        
        task_id = tasks[index]['id']
        with self.db.transaction() as conn:
            conn.execute("UPDATE tasks SET done = ? WHERE id = ?", (1 if done else 0, task_id))
            
        emit_event(self.db, "ticket.updated", "ticket", ticket_id, actor=None, data={"update_task": index, "done": done})
        return self.get(ticket_id)

    def add_acceptance_criteria(self, ticket_id: str, text: str) -> Ticket:
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT MAX(position) as max_pos FROM acceptance_criteria WHERE ticket_id = ?",
                (ticket_id,)
            ).fetchone()
            next_pos = (row['max_pos'] or 0) + 1
            
            conn.execute(
                "INSERT INTO acceptance_criteria (ticket_id, text, done, position) VALUES (?, ?, ?, ?)",
                (ticket_id, text, 0, next_pos)
            )
        emit_event(self.db, "ticket.updated", "ticket", ticket_id, actor=None, data={"add_ac": text})
        return self.get(ticket_id)

    def update_ac_status(self, ticket_id: str, index: int, done: bool) -> Ticket:
        criteria = self.db.execute(
            "SELECT id FROM acceptance_criteria WHERE ticket_id = ? ORDER BY position",
            (ticket_id,)
        ).fetchall()
        
        if index < 0 or index >= len(criteria):
            raise ValidationError(f"AC index {index} out of range (0-{len(criteria)-1})")
        
        ac_id = criteria[index]['id']
        with self.db.transaction() as conn:
            conn.execute("UPDATE acceptance_criteria SET done = ? WHERE id = ?", (1 if done else 0, ac_id))
            
        emit_event(self.db, "ticket.updated", "ticket", ticket_id, actor=None, data={"update_ac": index, "done": done})
        return self.get(ticket_id)

    def block(self, ticket_id: str, reason: str, actor: str | None = None) -> Ticket:
        ticket = self.transition(ticket_id, TicketStatus.BLOCKED.value, actor=actor)
        self.log(ticket_id, f"Blocked: {reason}", actor=actor)
        return ticket

    def get_next(self, tag: str | None = None, epic: str | None = None) -> Ticket | None:
        # This will be replaced by enhanced 'runnrr list' in Phase H
        # But for now we maintain compatibility
        tickets = self.list(status=TicketStatus.TODO.value, tag=tag, epic=epic)
        if not tickets:
            return None

        # Filter out blocked tickets (simplified for now)
        eligible = []
        for t in tickets:
            if not self._is_blocked(t.id):
                eligible.append(t)

        if not eligible:
            return None

        priority_order = {
            Priority.CRITICAL: 4,
            Priority.HIGH: 3,
            Priority.MEDIUM: 2,
            Priority.LOW: 1,
        }

        eligible.sort(key=lambda t: (
            -priority_order.get(t.priority, 0),
            t.estimated_effort,
            t.created_at
        ))

        return eligible[0]

    def describe(self, ticket_id: str) -> dict:
        ticket = self.get(ticket_id)
        return ticket.model_dump(mode="json")

    def _map_row_to_ticket(self, row: sqlite3.Row) -> Ticket:
        data = dict(row)
        ticket_id = data['id']
        
        # Load tags
        tag_rows = self.db.execute(
            "SELECT tag FROM tags WHERE entity_type = 'ticket' AND entity_id = ?",
            (ticket_id,)
        ).fetchall()
        data['tags'] = [r['tag'] for r in tag_rows]
        
        # Load tasks
        task_rows = self.db.execute(
            "SELECT text, done FROM tasks WHERE ticket_id = ? ORDER BY position",
            (ticket_id,)
        ).fetchall()
        data['tasks'] = [{"text": r['text'], "done": bool(r['done'])} for r in task_rows]
        
        # Load acceptance criteria
        ac_rows = self.db.execute(
            "SELECT text, done FROM acceptance_criteria WHERE ticket_id = ? ORDER BY position",
            (ticket_id,)
        ).fetchall()
        data['acceptance_criteria'] = [{"text": r['text'], "done": bool(r['done'])} for r in ac_rows]
        
        # Load execution log
        log_rows = self.db.execute(
            "SELECT created_at as timestamp, message, actor FROM log_entries WHERE entity_type = 'ticket' AND entity_id = ? ORDER BY created_at",
            (ticket_id,)
        ).fetchall()
        data['execution_log'] = [dict(r) for r in log_rows]
        
        # Load linked ADRs
        link_rows = self.db.execute(
            "SELECT target_id FROM links WHERE source_type = 'ticket' AND source_id = ? AND target_type = 'adr'",
            (ticket_id,)
        ).fetchall()
        data['linked_adrs'] = [r['target_id'] for r in link_rows]
        
        # Load blockers
        blocker_rows = self.db.execute(
            "SELECT blocked_by FROM dependencies WHERE ticket_id = ?",
            (ticket_id,)
        ).fetchall()
        data['blocked_by'] = [r['blocked_by'] for r in blocker_rows]
        data['dependencies'] = data['blocked_by'] # compatibility
        
        # We'll store the descriptive info separately for describe/list if needed
        self._blocker_details = [] 
        if data['blocked_by']:
            # This is a bit hacky, but we need to get titles/statuses for the CLI
            # We'll do it in describe() instead of map_row
            pass

        # Map fields
        data['epic'] = data.pop('epic_id')
        data['goal_text'] = data.pop('goal')
        data['notes_text'] = data.pop('notes')
        
        # Convert strings to types
        data['status'] = TicketStatus(data['status'])
        data['type'] = TicketType(data['type'])
        data['priority'] = Priority(data['priority'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        
        return Ticket(**data)

    def _update_tags(self, ticket_id: str, tags: list[str]):
        normalized_tags = [normalize_tag(t) for t in tags]
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM tags WHERE entity_type = 'ticket' AND entity_id = ?", (ticket_id,))
            for tag in normalized_tags:
                conn.execute(
                    "INSERT INTO tags (entity_type, entity_id, tag) VALUES (?, ?, ?)",
                    ("ticket", ticket_id, tag)
                )

    def _is_blocked(self, ticket_id: str) -> bool:
        row = self.db.execute(
            """
            SELECT COUNT(*) as count 
            FROM dependencies d
            JOIN tickets t ON d.blocked_by = t.id
            WHERE d.ticket_id = ? AND t.status != 'done'
            """,
            (ticket_id,)
        ).fetchone()
        return row['count'] > 0
