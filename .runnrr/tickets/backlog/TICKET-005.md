---
blocked_by: []
created_at: '2026-05-08T17:24:48Z'
dependencies: []
epic: EPIC-001
estimated_effort: 1
id: TICKET-005
linked_adrs: []
owner: null
priority: critical
status: backlog
tags:
- phase-f
title: Release Phase F (patch bump)
type: feature
updated_at: '2026-05-08T17:24:48Z'
---

# TICKET-005: Release Phase F (patch bump)

## Goal
Release the git isolation and removal changes as a patch version (v0.1.x+1).

## Tasks
- [ ] Bump version in `pyproject.toml`.
- [ ] Update `CHANGELOG.md` (if exists).
- [ ] Build and publish to PyPI.

## Acceptance Criteria
- [ ] New version is available on PyPI.
- [ ] Users can install it and `.runnrr/` is automatically ignored in their git repos.
