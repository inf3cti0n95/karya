# TICKET-013: Add tests for SQLite migration and ops

## Goal
Verify the stability and correctness of the SQLite-based storage layer and the migration process.

## Tasks
- [ ] Test: `runnrr init` creates `runnrr.db` with correct schema.
- [ ] Test: `runnrr migrate` correctly handles v0.1.x data and archives old files.
- [ ] Test: `runnrr migrate` refuses to run if DB is already initialized (without `--force`).
- [ ] Test: Creating entities (ticket, epic, ADR) creates correct rows in all related tables.
- [ ] Test: `runnrr export` produces valid markdown.
- [ ] Test: Concurrent reads work correctly (WAL mode).
- [ ] Test: Transaction rollback on failure (e.g., invalid insert).

## Acceptance Criteria
- [ ] All SQLite and migration tests pass.
- [ ] Data integrity is verified across all tables after operations.
