---
blocked_by: []
created_at: '2026-05-08T17:34:00Z'
dependencies: []
epic: EPIC-002
estimated_effort: 2
id: TICKET-006
linked_adrs: []
owner: null
priority: high
status: backlog
tags:
- phase-g
title: Implement SQLite Schema
type: feature
updated_at: '2026-05-08T17:34:00Z'
---

# TICKET-006: Implement SQLite Schema

## Goal
Establish the core data structure for runnrr v0.2.0 using SQLite to ensure data integrity, performance, and expressive querying.

## Tasks
- [ ] Create SQL schema for `tickets` table (id, title, status, type, priority, epic_id, owner, estimated_effort, goal, notes, created_at, updated_at).
- [ ] Create SQL schema for `epics` table (id, title, type, priority, owner, goal, success_metrics, notes, created_at, updated_at).
- [ ] Create SQL schema for `adrs` table (id, title, status, decision_date, context_text, decision_text, consequences, alternatives, supersedes, superseded_by, created_at, updated_at).
- [ ] Create SQL schema for `tags` table (entity_type, entity_id, tag).
- [ ] Create SQL schema for `tasks` table (ticket_id, text, done, position).
- [ ] Create SQL schema for `acceptance_criteria` table (ticket_id, text, done, position).
- [ ] Create SQL schema for `log_entries` table (entity_type, entity_id, message, actor, created_at).
- [ ] Create SQL schema for `dependencies` table (ticket_id, blocked_by).
- [ ] Create SQL schema for `links` table (source_type, source_id, target_type, target_id).
- [ ] Create SQL schema for `events` table (event_type, entity_type, entity_id, actor, data, created_at).
- [ ] Create FTS5 virtual table `search_index` (entity_type, entity_id, title, body, tags).

## Acceptance Criteria
- [ ] SQL schema is fully defined as per AGENTS.md Phase G.2.
- [ ] Schema includes foreign key constraints and necessary indexes.
- [ ] FTS5 is utilized for efficient searching.
