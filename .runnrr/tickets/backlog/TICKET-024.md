# TICKET-024: Add tests for CLI hardening

## Goal
Verify that the CLI hardening and safety measures are working correctly to prevent accidental data corruption or misuse.

## Tasks
- [ ] Test: `RunnrrClient` correctly finds parent `.runnrr/` from a nested subdirectory.
- [ ] Test: `RunnrrClient` raises `RunnrrNotInitializedError` when no `.runnrr/` is found.
- [ ] Test: `runnrr init` refuses to run in a project that already has `.runnrr/`.
- [ ] Test: `runnrr status` output correctly reflects the state of the database and git isolation.
- [ ] Test: Verify `Database` object is not accessible via public `RunnrrClient` interface.

## Acceptance Criteria
- [ ] All CLI hardening tests pass.
- [ ] System robustness is confirmed via automated tests.
