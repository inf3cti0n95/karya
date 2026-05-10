"""Link service for managing relationships between entities using SQLite."""

from __future__ import annotations

from pathlib import Path
from runnrr.core.db import Database, emit_event

class LinkService:
    def __init__(self, db: Database):
        self.db = db

    def link(self, source_id: str, target_id: str, actor: str | None = None) -> None:
        """Create a bidirectional link between two entities."""
        source_type = self._detect_type(source_id)
        target_type = self._detect_type(target_id)
        
        with self.db.transaction() as conn:
            # Check if already exists
            exists = conn.execute(
                "SELECT 1 FROM links WHERE source_type = ? AND source_id = ? AND target_type = ? AND target_id = ?",
                (source_type, source_id, target_type, target_id)
            ).fetchone()
            
            if exists:
                return

            conn.execute(
                "INSERT INTO links (source_type, source_id, target_type, target_id) VALUES (?, ?, ?, ?)",
                (source_type, source_id, target_type, target_id)
            )
            conn.execute(
                "INSERT INTO links (source_type, source_id, target_type, target_id) VALUES (?, ?, ?, ?)",
                (target_type, target_id, source_type, source_id)
            )
            
            # Special case: ticket <-> epic link updates the ticket.epic_id column
            if source_type == "ticket" and target_type == "epic":
                conn.execute("UPDATE tickets SET epic_id = ? WHERE id = ?", (target_id, source_id))
            elif source_type == "epic" and target_type == "ticket":
                conn.execute("UPDATE tickets SET epic_id = ? WHERE id = ?", (source_id, target_id))
            
        emit_event(self.db, f"{source_type}.linked", source_type, source_id, actor, 
                   data={"target_id": target_id, "target_type": target_type})
        emit_event(self.db, f"{target_type}.linked", target_type, target_id, actor, 
                   data={"target_id": source_id, "target_type": source_type})

    def _detect_type(self, entity_id: str) -> str:
        if entity_id.startswith("TICKET-"):
            return "ticket"
        if entity_id.startswith("EPIC-"):
            return "epic"
        if entity_id.startswith("ADR-"):
            return "adr"
        raise ValueError(f"Unknown entity ID format: {entity_id}")
