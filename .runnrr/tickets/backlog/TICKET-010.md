# TICKET-010: Implement Event Log (SQLite)

## Goal
Replace the Git-based audit trail with a structured SQLite event log for better traceability and easier auditing.

## Tasks
- [ ] Implement `emit_event(db, event_type, entity_type, entity_id, actor, data)` function.
- [ ] Integrate `emit_event` into all service mutation methods (create, update, transition, link, etc.).
- [ ] Implement `runnrr events` CLI command with filters (`--ticket`, `--since`).
- [ ] Implement `--json` output for `runnrr events`.

## Acceptance Criteria
- [ ] Every mutation in the system is recorded in the `events` table.
- [ ] `runnrr events` correctly displays the history of changes.
- [ ] Event data (JSON) allows for detailed auditing of what changed.
