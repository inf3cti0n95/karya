---
blocked_by: []
created_at: '2026-05-08T17:44:02Z'
dependencies: []
epic: EPIC-002
estimated_effort: 1
id: TICKET-016
linked_adrs: []
owner: null
priority: high
status: backlog
tags:
- phase-h
title: Implement runnrr list --blocked detail view
type: feature
updated_at: '2026-05-08T17:44:02Z'
---

# TICKET-016: Implement runnrr list --blocked detail view

## Goal
Help users identify bottlenecks by showing exactly what is blocking each ticket.

## Tasks
- [ ] Implement `runnrr list --blocked` flag.
- [ ] Query for tickets with `blocked` status.
- [ ] For each blocked ticket, list the IDs and titles of tickets blocking it.

## Acceptance Criteria
- [ ] `runnrr list --blocked` displays blocked tickets and their blockers correctly.
- [ ] Information is helpful for unblocking work.
