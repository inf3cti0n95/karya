# TICKET-020: Enforce runnrr root discovery for all mutations

## Goal
Enable `runnrr` to be used from any subdirectory within a project by automatically discovering the project root (where `.runnrr/` lives).

## Tasks
- [ ] Implement `_find_runnrr_root(start: Path) -> Path` to walk up the directory tree.
- [ ] Ensure all CLI commands that mutate or read data use this discovery logic.
- [ ] Raise `RunnrrNotInitializedError` if `.runnrr/` is not found.

## Acceptance Criteria
- [ ] `runnrr list`, `runnrr start`, etc. work correctly when executed from a nested subdirectory of the project.
- [ ] Clear error message is shown if `runnrr` is run outside of an initialized project.
