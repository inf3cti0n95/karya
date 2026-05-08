---
blocked_by: []
created_at: '2026-05-08T17:34:02Z'
dependencies: []
epic: EPIC-002
estimated_effort: 3
id: TICKET-008
linked_adrs: []
owner: null
priority: high
status: backlog
tags:
- phase-g
title: Implement runnrr migrate command
type: feature
updated_at: '2026-05-08T17:34:02Z'
---

# TICKET-008: Implement runnrr migrate command

## Goal
Provide a seamless transition for users from v0.1.x (markdown-based) to v0.2.0 (SQLite-based).

## Tasks
- [ ] Implement `runnrr migrate` command in CLI.
- [ ] Detect existing v0.1.x layout (`.runnrr/tickets/`, etc.).
- [ ] Use existing parser to read all `.md` files.
- [ ] Insert all data into the new SQLite database.
- [ ] Rename old directories to `.runnrr/archive_v01/`.
- [ ] Add safety check to prevent re-migration if DB already has data (unless `--force`).

## Acceptance Criteria
- [ ] `runnrr migrate` successfully imports all tickets, epics, and ADRs.
- [ ] Old data is preserved in the archive directory.
- [ ] The CLI provides clear progress and summary messages.
