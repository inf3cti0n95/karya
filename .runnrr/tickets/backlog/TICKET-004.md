# TICKET-004: Add tests for Git Isolation

## Goal
Verify that the git isolation and removal changes work as expected and prevent regressions.

## Tasks
- [ ] Create a test suite for `runnrr init` behavior regarding git isolation.
- [ ] Test: `runnrr init` in a temp dir with a parent `.git/` → `.gitignore` gets `.runnrr/` added.
- [ ] Test: `runnrr init` when `.runnrr/` already in `.gitignore` → no duplicate entry added.
- [ ] Test: `runnrr init` with no `.git/` anywhere in the tree → no error, just a printed notice.
- [ ] Test: `runnrr init` in a subdirectory of a git repo → finds the parent `.git/`, adds to correct `.gitignore`.
- [ ] Test: `import gitpython` anywhere in the codebase → test fails (grep-based test).

## Acceptance Criteria
- [ ] All new tests pass.
- [ ] Automated check for `gitpython` imports is integrated into the test suite.
