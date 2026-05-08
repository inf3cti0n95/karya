# TICKET-023: Implement RunnrrNotInitializedError

## Goal
Improve error handling and user feedback by providing a specific exception when `runnrr` operations are attempted outside of an initialized project.

## Tasks
- [ ] Add `RunnrrNotInitializedError` to `src/runnrr/exceptions.py`.
- [ ] Update CLI error handling to catch this error and print a helpful instruction (e.g., "Run `runnrr init` first").

## Acceptance Criteria
- [ ] Attempting to run `runnrr` in a non-project directory results in a clear `RunnrrNotInitializedError`-based message.
