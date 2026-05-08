---
blocked_by: []
created_at: '2026-05-08T17:54:26Z'
dependencies: []
epic: EPIC-002
estimated_effort: 1
id: TICKET-026
linked_adrs: []
owner: null
priority: medium
status: backlog
tags:
- phase-i
title: Implement runnrr init guard
type: feature
updated_at: '2026-05-08T17:54:26Z'
---

# TICKET-026: Implement runnrr init guard

## Goal
Prevent nested or duplicate runnrr initialization by checking for an existing `.runnrr/` directory in the current or any parent directory.

## Tasks
- [ ] Update `runnrr init` logic to use `_find_runnrr_root()`.
- [ ] If an existing `.runnrr/` is found, print an error and exit.

## Acceptance Criteria
- [ ] `runnrr init` fails gracefully with a clear error message if the project is already initialized.
