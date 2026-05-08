# TICKET-019: Implement runnrr init guard

## Goal
Prevent nested or duplicate runnrr initialization by checking for an existing `.runnrr/` directory in the current or any parent directory.

## Tasks
- [ ] Update `runnrr init` logic to use `_find_runnrr_root()`.
- [ ] If an existing `.runnrr/` is found, print an error and exit.

## Acceptance Criteria
- [ ] `runnrr init` fails gracefully with a clear error message if the project is already initialized.
