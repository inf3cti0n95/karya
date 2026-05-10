"""Search service using SQLite FTS5 index."""

from __future__ import annotations

from typing import Dict, Any, List
from runnrr.core.db import Database

class SearchService:
    def __init__(self, db: Database):
        self.db = db

    def rebuild_index(self) -> None:
        """
        Rebuild the FTS5 search index from source tables.
        Note: In normal operation (v0.2.0), mutations update the index incrementally.
        This is for recovery or initial migration.
        """
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM search_index")
            
            # Tickets
            conn.execute("""
                INSERT INTO search_index (entity_type, entity_id, title, body, tags)
                SELECT 'ticket', id, title, IFNULL(goal, '') || ' ' || IFNULL(notes, ''),
                (SELECT GROUP_CONCAT(tag, ' ') FROM tags WHERE entity_type = 'ticket' AND entity_id = t.id)
                FROM tickets t
            """)
            
            # Epics
            conn.execute("""
                INSERT INTO search_index (entity_type, entity_id, title, body, tags)
                SELECT 'epic', id, title, IFNULL(goal, '') || ' ' || IFNULL(notes, ''),
                (SELECT GROUP_CONCAT(tag, ' ') FROM tags WHERE entity_type = 'epic' AND entity_id = e.id)
                FROM epics e
            """)
            
            # ADRs
            conn.execute("""
                INSERT INTO search_index (entity_type, entity_id, title, body, tags)
                SELECT 'adr', id, title, 
                IFNULL(context_text, '') || ' ' || IFNULL(decision_text, '') || ' ' || IFNULL(consequences, ''),
                (SELECT GROUP_CONCAT(tag, ' ') FROM tags WHERE entity_type = 'adr' AND entity_id = a.id)
                FROM adrs a
            """)

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Perform a full-text search across all entities."""
        rows = self.db.execute(
            """
            SELECT entity_type as type, entity_id as id, title
            FROM search_index 
            WHERE search_index MATCH ?
            ORDER BY rank
            """,
            (query,)
        ).fetchall()
        return [dict(row) for row in rows]
        
    def find_related(self, entity_id: str) -> List[Dict[str, Any]]:
        """Find entities with overlapping tags."""
        # Get tags for the entity
        tag_rows = self.db.execute(
            "SELECT tag FROM tags WHERE entity_id = ?",
            (entity_id,)
        ).fetchall()
        tags = [r['tag'] for r in tag_rows]
        
        if not tags:
            return []
            
        placeholders = ','.join(['?'] * len(tags))
        rows = self.db.execute(
            f"""
            SELECT entity_id as id, entity_type as type, COUNT(tag) as overlap
            FROM tags
            WHERE tag IN ({placeholders}) AND entity_id != ?
            GROUP BY entity_id, entity_type
            ORDER BY overlap DESC
            LIMIT 10
            """,
            (*tags, entity_id)
        ).fetchall()
        
        return [dict(row) for row in rows]
