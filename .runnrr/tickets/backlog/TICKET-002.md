# TICKET-002: Implement runnrr init git isolation

## Goal
Protect the host project from accidentally tracking the `.runnrr/` directory by automatically adding it to the project's `.gitignore`.

## Tasks
- [ ] Implement `_find_host_gitignore(start: Path) -> Path | None` to walk up from cwd to find `.git/` and its corresponding `.gitignore`.
- [ ] Implement `_ensure_gitignore_entry(gitignore_path: Path, entry: str) -> None` to safely add `.runnrr/` to `.gitignore`.
- [ ] Update `init_runnrr(root: Path)` in `src/runnrr/core/filesystem.py` to call these functions.
- [ ] Add informative print statements for success or missing git repository.

## Acceptance Criteria
- [ ] `runnrr init` in a directory with a parent `.git/` adds `.runnrr/` to the parent's `.gitignore`.
- [ ] `runnrr init` does not add duplicate entries to `.gitignore`.
- [ ] `runnrr init` without a `.git/` anywhere in the tree prints a notice instead of failing.
- [ ] `runnrr init` in a subdirectory of a git repo finds the correct parent `.gitignore`.
