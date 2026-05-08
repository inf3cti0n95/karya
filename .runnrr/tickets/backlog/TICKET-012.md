# TICKET-012: SQLite-based ID generation

## Goal
Replace the filesystem-based ID scanning with efficient SQLite queries for generating the next TICKET-XXX, EPIC-XXX, or ADR-XXX ID.

## Tasks
- [ ] Implement `next_ticket_id(db: Database) -> str`.
- [ ] Implement `next_epic_id(db: Database) -> str`.
- [ ] Implement `next_adr_id(db: Database) -> str`.
- [ ] Ensure the logic correctly handles empty tables and leading zeros (e.g., TICKET-001).

## Acceptance Criteria
- [ ] New IDs are generated correctly and sequentially.
- [ ] ID generation is fast and does not depend on the filesystem.
- [ ] Collisions are prevented by SQLite's transaction model.
