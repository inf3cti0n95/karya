---
blocked_by: []
created_at: '2026-05-08T17:24:44Z'
dependencies: []
epic: EPIC-001
estimated_effort: 1
id: TICKET-001
linked_adrs: []
owner: null
priority: critical
status: in-progress
tags:
- phase-f
title: Remove gitpython dependency
type: feature
updated_at: '2026-05-08T17:57:57.234845Z'
---

## Goal

Stop using `gitpython` entirely to avoid breaking the host project's git repository and simplify dependencies.

## Tasks

- [ ] Remove `gitpython` from `pyproject.toml`
- [ ] Delete `src/runnrr/git/` directory
- [ ] Remove all imports of `GitIntegration` from the codebase
- [ ] Remove all `self._git.commit(...)` calls from services
- [ ] Remove `ensure_repo()` calls from `src/runnrr/core/filesystem.py`
- [ ] Run `grep -r "gitpython\|GitIntegration\|git\.commit\|Repo(" src/runnrr/` to confirm zero results

## Acceptance Criteria

- [ ] `gitpython` is no longer in `pyproject.toml`
- [ ] `src/runnrr/git/` is deleted
- [ ] Codebase compiles and runs without git-related errors
- [ ] Grep search for gitpython-related terms returns no results

## Log



## Notes