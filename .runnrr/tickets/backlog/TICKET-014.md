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
