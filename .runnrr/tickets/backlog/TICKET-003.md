---
blocked_by: []
created_at: '2026-05-08T17:24:46Z'
dependencies: []
epic: EPIC-001
estimated_effort: 1
id: TICKET-003
linked_adrs: []
owner: null
priority: critical
status: backlog
tags:
- phase-f
title: Remove git from event log
type: feature
updated_at: '2026-05-08T17:24:46Z'
---

# TICKET-003: Remove git from event log

## Goal
Decouple the event logging system from Git by removing automatic git commits during mutations.

## Tasks
- [ ] Identify all locations where `self._git.commit()` or similar is called during mutations.
- [ ] Remove these calls.
- [ ] Ensure the system still logs events (in-memory or to log files as per current v0.1.x implementation) without requiring a git commit.

## Acceptance Criteria
- [ ] No git commits are performed when creating, updating, or transitioning tickets.
- [ ] The CLI does not fail due to missing git repository or git-related errors during normal operations.
