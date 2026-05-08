---
blocked_by: []
created_at: '2026-05-08T17:44:01Z'
dependencies: []
epic: EPIC-002
estimated_effort: 2
id: TICKET-015
linked_adrs: []
owner: null
priority: high
status: backlog
tags:
- phase-h
title: Enhance runnrr list default view
type: feature
updated_at: '2026-05-08T17:44:01Z'
---

# TICKET-015: Enhance runnrr list default view

## Goal
Make `runnrr list` the primary way to understand what to work on next by providing a clear, prioritized view of actionable tickets.

## Tasks
- [ ] Update `runnrr list` to show `todo` and `in-progress` status by default.
- [ ] Implement sorting: `in-progress` first, then `todo` by priority (critical → low), then effort (low → high).
- [ ] Improve human-readable output using `Rich` for better formatting (symbols, colors).
- [ ] Add summary counts (blocked, backlog, done).

## Acceptance Criteria
- [ ] `runnrr list` (no flags) shows actionable tickets in the correct order.
- [ ] The output is visually clear and provides a good "state of the world" overview.
