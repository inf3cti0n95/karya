---
blocked_by: []
created_at: '2026-05-08T17:54:30Z'
dependencies: []
epic: EPIC-002
estimated_effort: 1
id: TICKET-030
linked_adrs: []
owner: null
priority: low
status: backlog
tags:
- phase-i
title: Implement RunnrrNotInitializedError
type: feature
updated_at: '2026-05-08T17:54:30Z'
---

# TICKET-030: Implement RunnrrNotInitializedError

## Goal
Improve error handling and user feedback by providing a specific exception when `runnrr` operations are attempted outside of an initialized project.

## Tasks
- [ ] Add `RunnrrNotInitializedError` to `src/runnrr/exceptions.py`.
- [ ] Update CLI error handling to catch this error and print a helpful instruction (e.g., "Run `runnrr init` first").

## Acceptance Criteria
- [ ] Attempting to run `runnrr` in a non-project directory results in a clear `RunnrrNotInitializedError`-based message.
