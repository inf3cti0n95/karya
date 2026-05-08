# TICKET-015: Enhance runnrr list default view

## Goal
Make `runnrr list` the primary way to understand what to work on next by providing a clear, prioritized view of actionable tickets.

## Tasks
- [ ] Update `runnrr list` to show `todo` and `in-progress` status by default.
- [ ] Implement sorting: `in-progress` first, then `todo` by priority (critical → low), then effort (low → high).
- [ ] Improve human-readable output using `Rich` for better formatting (symbols, colors).
- [ ] Add summary counts (blocked, backlog, done).

## Acceptance Criteria
- [ ] `runnrr list` (no flags) shows actionable tickets in the correct order.
- [ ] The output is visually clear and provides a good "state of the world" overview.
