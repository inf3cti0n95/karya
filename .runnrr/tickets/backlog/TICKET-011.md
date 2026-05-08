---
blocked_by: []
created_at: '2026-05-08T17:34:05Z'
dependencies: []
epic: EPIC-002
estimated_effort: 2
id: TICKET-011
linked_adrs: []
owner: null
priority: high
status: backlog
tags:
- phase-g
title: Implement .md export on demand
type: feature
updated_at: '2026-05-08T17:34:05Z'
---

# TICKET-011: Implement .md export on demand

## Goal
Allow users to generate markdown files from the SQLite data for documentation, sharing, or review purposes, while maintaining SQLite as the source of truth.

## Tasks
- [ ] Implement `export_ticket_md()`, `export_epic_md()`, `export_adr_md()` in `filesystem.py` (utilizing `parser.py`).
- [ ] Implement `runnrr export` CLI command.
- [ ] Support exporting single entities and `--all`.
- [ ] Support redirecting output to a file or directory via `--out`.

## Acceptance Criteria
- [ ] `runnrr export` generates valid markdown files with correct frontmatter.
- [ ] Exported files are consistent with the data in the SQLite database.
- [ ] The system remains SQLite-centric; editing exported files has no effect on the database.
