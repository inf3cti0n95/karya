---
blocked_by: []
created_at: '2026-05-08T17:54:29Z'
dependencies: []
epic: EPIC-002
estimated_effort: 1
id: TICKET-029
linked_adrs: []
owner: null
priority: medium
status: backlog
tags:
- phase-i
title: Add --db-path support for agents
type: feature
updated_at: '2026-05-08T17:54:29Z'
---

# TICKET-029: Add --db-path support for agents

## Goal
Support non-standard working directory environments (like CI/CD) by allowing agents to explicitly specify the location of the runnrr database.

## Tasks
- [ ] Add `--db-path` optional flag to relevant CLI commands.
- [ ] Update `RunnrrClient` to accept an explicit database path.
- [ ] Ensure validation still occurs even with an explicit path.

## Acceptance Criteria
- [ ] `runnrr` commands work correctly when given an explicit `--db-path`, regardless of the current working directory.
