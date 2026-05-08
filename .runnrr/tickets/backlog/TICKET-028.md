---
blocked_by: []
created_at: '2026-05-08T17:54:28Z'
dependencies: []
epic: EPIC-002
estimated_effort: 2
id: TICKET-028
linked_adrs: []
owner: null
priority: high
status: backlog
tags:
- phase-i
title: Implement runnrr status command
type: feature
updated_at: '2026-05-08T17:54:28Z'
---

# TICKET-028: Implement runnrr status command

## Goal
Provide a quick overview of the runnrr workspace health and summary statistics.

## Tasks
- [ ] Implement `runnrr status` CLI command.
- [ ] Display project root path.
- [ ] Display database file and health (size, schema version).
- [ ] Display summary counts for tickets, epics, and ADRs.
- [ ] Display host git isolation status.

## Acceptance Criteria
- [ ] `runnrr status` provides an accurate and helpful summary of the workspace.
