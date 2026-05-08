---
blocked_by: []
created_at: '2026-05-08T17:34:01Z'
dependencies: []
epic: EPIC-002
estimated_effort: 2
id: TICKET-007
linked_adrs: []
owner: null
priority: high
status: backlog
tags:
- phase-g
title: Implement Database core class
type: feature
updated_at: '2026-05-08T17:34:01Z'
---

# TICKET-007: Implement Database core class

## Goal
Create a robust Python interface for interacting with the SQLite database, handling connections, transactions, and migrations.

## Tasks
- [ ] Create `src/runnrr/core/db.py`.
- [ ] Implement `Database` class with `__init__(db_path)`.
- [ ] Implement `connect()` method (enable WAL mode, foreign keys, row_factory).
- [ ] Implement `migrate()` method with schema version tracking (PRAGMA user_version).
- [ ] Implement `_run_initial_schema()` to execute the schema from TICKET-006.
- [ ] Implement `transaction()` context manager for atomic operations.
- [ ] Implement `execute(sql, params)` wrapper.

## Acceptance Criteria
- [ ] `Database` class correctly manages SQLite lifecycle.
- [ ] Initial migration successfully creates all tables.
- [ ] WAL mode is enabled for concurrent access.
- [ ] Foreign key constraints are enforced.
