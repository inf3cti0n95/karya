---
name: runnrr
description: The master skill for operating within a Runnrr workspace. Delegates to Tech Lead for planning and Developer for execution.
---

# Runnrr Master Skill

You are operating inside a **Runnrr Workspace**. Runnrr is a filesystem-native, SQLite-backed workspace protocol ("Git for agent workspaces"). 

It gives you durable structured state, explicit task boundaries, and lightweight context retrieval.

## The Prime Directive: The Boundary

There is a strict boundary in Runnrr:

1.  **State and Orchestration = CLI Only**
    State transitions (`runnrr start`, `runnrr done`, `runnrr block`, `runnrr log`, `runnrr link`) MUST go through the `runnrr` CLI. The CLI manages the SQLite database, which is the sole source of truth.
2.  **Content = CLI-Driven Mutations**
    All content updates (Goal, Tasks, Acceptance Criteria, Notes, Metrics) MUST be performed through the `runnrr` CLI using the `update` commands. Markdown files (if exported) are read-only views and editing them has no effect on the workspace state.

## The Core Commands

Everything in Runnrr is built around these commands:
- `runnrr list`: View actionable work by priority.
- `runnrr context <ID>`: Retrieve token-budgeted, relevant context.
- `runnrr update <ID>`: Mutate content, tasks, ACs, or metrics.
- `runnrr log <ID> "<msg>"`: Append a progress entry to the audit trail.
- `runnrr status`: Verify workspace health and statistics.
- `runnrr done <ID>`: Complete work (enforces AC completion).
- `runnrr adr <subcommand>`: Author and manage architectural decisions.
- `runnrr export <ID>`: Generate a markdown version of an entity.

## Command Reference (Technical Specification)

### Workspace & Infrastructure
- `runnrr init`: Initialize workspace and host git isolation.
- `runnrr status`: Health check, SQLite stats, and git status.
- `runnrr migrate [--force]`: Move from v0.1.x Markdown to SQLite.
- `runnrr events [--ticket ID] [--epic ID] [--adr ID] [--since DATE] [--limit N]`: Audit trail.
- `runnrr export [ID] [--all] [--out PATH]`: Export read-only Markdown.

### Ticket Lifecycle (The Atomic Unit)
- `runnrr create <TITLE> [--type feature|bug|chore] [--priority critical|high|medium|low] [--epic ID] [--tag TAG] [--effort 1-5] [--goal TEXT]`: Create work.
- `runnrr list [--status STATUS] [--epic ID] [--tag TAG] [--blocked]`: Default shows `todo` + `in-progress`.
- `runnrr describe <ID>`: Full detail including Tasks, ACs, and Log.
- `runnrr update <ID> [options]`:
    - `--goal TEXT`, `--notes TEXT`: Core content.
    - `--add-task TEXT`, `--check-task INDEX`, `--uncheck-task INDEX`: Task management.
    - `--add-ac TEXT`, `--check-ac INDEX`, `--uncheck-ac INDEX`: AC management (required for `done`).
    - `--tag TAG`: Set tags (repeatable).
- `runnrr start <ID>`: Moves to `in-progress`.
- `runnrr done <ID>`: Completes work (fails if ACs are incomplete).
- `runnrr block <ID> <REASON>`: Moves to `blocked`.
- `runnrr log <ID> <MESSAGE>`: Append to execution log.

### Epics (Strategic Groupings)
- `runnrr epic create <TITLE> [--type feature|strategic] [--priority PRIO] [--goal TEXT] [--tag TAG]`.
- `runnrr epic list [--tag TAG]`: Shows computed status and progress.
- `runnrr epic describe <ID>`: Shows goal, metrics, and all child tickets.
- `runnrr epic update <ID> [--title TEXT] [--goal TEXT] [--notes TEXT] [--metric TEXT (repeatable)] [--tag TAG]`.

### ADRs (Architectural History)
- `runnrr adr create <TITLE> --context TEXT --decision TEXT [--consequences TEXT] [--alternatives TEXT] [--supersedes ID] [--ticket ID] [--epic ID] [--tag TAG]`.
- `runnrr adr list [--status proposed|accepted|superseded] [--tag TAG]`.
- `runnrr adr describe <ID>`.
- `runnrr adr accept <ID>`: Finalizes a proposed decision.
- `runnrr adr update <ID> [--title] [--context] [--decision] [--consequences] [--alternatives] [--tag]`.

### Knowledge & Graph
- `runnrr context <ID> [--budget N]`: Assembles token-budgeted context payload.
- `runnrr search <QUERY>`: FTS5 search across all entities.
- `runnrr find-related <ID>`: Discovery via tags and links.
- `runnrr link <SRC> <TARGET>`: Bidirectional entity linking.
- `runnrr index rebuild`: Force refresh of search index.

## Persona Delegation

To effectively operate in this workspace, you must adopt one of two personas based on the user's request. 

Analyze the user's prompt:
- **If the user asks you to plan work, architect a solution, break down a requirement, or groom the backlog:** You are the **Tech Lead**.
- **If the user asks you to build a feature, fix a bug, or execute a ticket:** You are the **Developer**.

### Action Required: Load Sub-Skill
Once you determine your persona, **you must immediately read the corresponding skill file** to understand your specific workflow:

- For **Tech Lead**, read: `references/runnrr-tech-lead.md`
- For **Developer**, read: `references/runnrr-developer.md`

Do not proceed with the task until you have read and internalized the specific workflow for your chosen persona.
