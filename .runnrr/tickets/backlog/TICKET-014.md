---
blocked_by: []
created_at: '2026-05-08T17:44:00Z'
dependencies: []
epic: EPIC-002
estimated_effort: 1
id: TICKET-014
linked_adrs: []
owner: null
priority: medium
status: backlog
tags:
- phase-h
title: Remove exec and next commands
type: feature
updated_at: '2026-05-08T17:44:00Z'
---

# TICKET-014: Remove exec and next commands

## Goal
Simplify the CLI interface by removing redundant or less useful commands, favoring a more powerful `list` command.

## Tasks
- [ ] Remove `@cli.command("exec")` from `src/runnrr/cli/main.py`.
- [ ] Remove `@cli.command("next")` from `src/runnrr/cli/main.py`.
- [ ] Remove `ticket_service.get_next()` and any associated logic.
- [ ] Remove any exec-bundling logic from services.

## Acceptance Criteria
- [ ] `runnrr exec` and `runnrr next` are no longer available in the CLI.
- [ ] Codebase is cleaned of unused logic related to these commands.
