import os
from pathlib import Path
from runnrr.core.db import Database

def test_db_init(tmp_path):
    db_path = tmp_path / "runnrr.db"
    db = Database(db_path)
    db.connect()
    db.migrate()
    
    # Check if tables exist
    tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = [t['name'] for t in tables]
    
    expected_tables = [
        'tickets', 'epics', 'adrs', 'tags', 'tasks', 
        'acceptance_criteria', 'log_entries', 'dependencies', 
        'links', 'events'
    ]
    for table in expected_tables:
        assert table in table_names
    
    # Check FTS5 table
    fts_tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='search_index'").fetchone()
    assert fts_tables is not None

    # Check version
    version = db.execute("PRAGMA user_version").fetchone()[0]
    assert version == 1
    
    db.close()

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
