---
blocked_by: []
created_at: '2026-05-08T17:44:03Z'
dependencies: []
epic: EPIC-002
estimated_effort: 1
id: TICKET-017
linked_adrs: []
owner: null
priority: high
status: backlog
tags:
- phase-h
title: Enhance runnrr list --json for agents
type: feature
updated_at: '2026-05-08T17:44:03Z'
---

# TICKET-017: Enhance runnrr list --json for agents

## Goal
Provide a machine-readable view of the task list that allows agents to autonomously decide what to work on next.

## Tasks
- [ ] Implement `--json` flag for `runnrr list`.
- [ ] Ensure the JSON output includes ticket details (id, title, status, priority, tags, epic_id, owner, task counts, criteria counts).
- [ ] Include a `summary` object with counts for each status.

## Acceptance Criteria
- [ ] `runnrr list --json` returns valid JSON matching the format in AGENTS.md Phase H.2.
- [ ] Agent can parse this output to find the next available task.
