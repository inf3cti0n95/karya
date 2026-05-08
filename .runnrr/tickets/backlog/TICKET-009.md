# TICKET-009: Rewrite services to use DB

## Goal
Switch the primary data source and storage from the filesystem to the SQLite database across all services.

## Tasks
- [ ] Update `TicketService` to use `Database` for all CRUD operations.
- [ ] Update `EpicService` to use `Database`.
- [ ] Update `ADRService` to use `Database`.
- [ ] Update `ContextService` to read context from `Database`.
- [ ] Update `SearchService` to use FTS5 virtual table in `Database`.
- [ ] Remove `filesystem.write_ticket_file()`, `filesystem.parse_ticket()` calls.
- [ ] Ensure `parser.py` is only used for export (not reading from disk).

## Acceptance Criteria
- [ ] All services successfully perform operations using the SQLite database.
- [ ] Data persistency is confirmed via CLI commands.
- [ ] Performance of list and search operations is improved.
