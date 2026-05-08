"""Database and Search index for Runnrr."""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Any
from runnrr.core.filesystem import normalize_root

DB_FILE = ".db"

def get_db(root: Path) -> sqlite3.Connection:
    root = normalize_root(root)
    db_path = root / ".runnrr" / DB_FILE
    
    # Connect and initialize if needed
    init_needed = not db_path.exists()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    if init_needed:
        _init_schema(conn)
        
    return conn

def _init_schema(conn: sqlite3.Connection):
    cursor = conn.cursor()
    
    # FTS5 Virtual Table
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
            id, type, title, status, content, tags
        )
    """)
    
    # Tag mapping table for exact lookups
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entity_tags (
            entity_id TEXT,
            entity_type TEXT,
            tag TEXT,
            PRIMARY KEY (entity_id, tag)
        )
    """)
    
    conn.commit()

def rebuild_index(root: Path):
    from runnrr.services.ticket_service import TicketService
    from runnrr.services.epic_service import EpicService
    from runnrr.services.adr_service import ADRService
    
    conn = get_db(root)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM search_index")
    cursor.execute("DELETE FROM entity_tags")
    
    # Tickets
    ts = TicketService(root)
    for ticket in ts.list():
        content = f"{ticket.goal_text or ''} {ticket.notes_text or ''}"
        for t in ticket.tasks:
            content += f" {t.get('text', '')}"
        for ac in ticket.acceptance_criteria:
            content += f" {ac.get('text', '')}"
            
        tags_str = " ".join(ticket.tags)
        cursor.execute(
            "INSERT INTO search_index (id, type, title, status, content, tags) VALUES (?, ?, ?, ?, ?, ?)",
            (ticket.id, "ticket", ticket.title, ticket.status.value, content, tags_str)
        )
        for tag in ticket.tags:
            cursor.execute(
                "INSERT INTO entity_tags (entity_id, entity_type, tag) VALUES (?, ?, ?)",
                (ticket.id, "ticket", tag)
            )

    # Epics
    es = EpicService(root)
    for epic in es.list():
        content = f"{epic.goal_text or ''} {epic.notes_text or ''}"
        for sm in epic.success_metrics:
            content += f" {sm}"
            
        tags_str = " ".join(epic.tags)
        # Epic status is computed, we'll just put "active" or its type for index
        cursor.execute(
            "INSERT INTO search_index (id, type, title, status, content, tags) VALUES (?, ?, ?, ?, ?, ?)",
            (epic.id, "epic", epic.title, "active", content, tags_str)
        )
        for tag in epic.tags:
            cursor.execute(
                "INSERT INTO entity_tags (entity_id, entity_type, tag) VALUES (?, ?, ?)",
                (epic.id, "epic", tag)
            )

    # ADRs
    as_svc = ADRService(root)
    for adr in as_svc.list():
        content = f"{adr.context_text or ''} {adr.decision_text or ''} {adr.consequences_text or ''} {adr.alternatives_text or ''}"
        tags_str = " ".join(adr.tags)
        
        cursor.execute(
            "INSERT INTO search_index (id, type, title, status, content, tags) VALUES (?, ?, ?, ?, ?, ?)",
            (adr.id, "adr", adr.title, adr.status.value, content, tags_str)
        )
        for tag in adr.tags:
            cursor.execute(
                "INSERT INTO entity_tags (entity_id, entity_type, tag) VALUES (?, ?, ?)",
                (adr.id, "adr", tag)
            )

    conn.commit()

def search(root: Path, query: str) -> List[Dict[str, Any]]:
    conn = get_db(root)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, type, title, status, tags
        FROM search_index 
        WHERE search_index MATCH ?
        ORDER BY rank
    """, (query,))
    
    return [dict(row) for row in cursor.fetchall()]

def find_related(root: Path, entity_id: str) -> List[Dict[str, Any]]:
    conn = get_db(root)
    cursor = conn.cursor()
    
    # Get tags for the entity
    cursor.execute("SELECT tag FROM entity_tags WHERE entity_id = ?", (entity_id,))
    tags = [row['tag'] for row in cursor.fetchall()]
    
    if not tags:
        return []
        
    # Find entities with overlapping tags, ordered by overlap count
    placeholders = ','.join(['?'] * len(tags))
    cursor.execute(f"""
        SELECT entity_id as id, entity_type as type, COUNT(tag) as overlap
        FROM entity_tags
        WHERE tag IN ({placeholders}) AND entity_id != ?
        GROUP BY entity_id, entity_type
        ORDER BY overlap DESC
        LIMIT 10
    """, (*tags, entity_id))
    
    return [dict(row) for row in cursor.fetchall()]