# Runnrr

```
Git for agent workspaces.
```

Runnrr is a filesystem-native, SQLite-backed workspace protocol that provides coding agents and humans with durable structured state, explicit task boundaries, and lightweight context retrieval.

## The Stack

```
.runnrr/              The Workspace Root.
├── runnrr.db        SQLite database. Primary source of truth.
├── archive_v01/     Archived v0.1.x markdown files (post-migration).
└── context/         Project-wide conventions and context.
```

**The Boundary Rule:** The CLI is the exclusive write path for all state and content. Exported markdown files are read-only views; direct modifications to these files will not be reflected in the workspace state.

## Command Reference

### Workspace Commands
- `runnrr init`: Initialize a new workspace.
- `runnrr status`: View workspace health, statistics, and git isolation status.
- `runnrr migrate [--force]`: Migrate from v0.1.x markdown storage to SQLite.
- `runnrr events [--ticket ID] [--epic ID] [--adr ID] [--since DATE] [--limit N]`: View the append-only audit trail.
- `runnrr export [ID] [--all] [--out PATH]`: Export entities as markdown.

### Ticket Management
- `runnrr create <TITLE> [--type TYPE] [--priority PRIO] [--epic ID] [--tag TAG] [--effort N] [--goal TEXT]`: Create a new ticket.
- `runnrr list [--status STATUS] [--epic ID] [--tag TAG] [--blocked]`: View tickets. Default shows `actionable` work.
- `runnrr describe <ID>`: View full ticket details, including tasks, ACs, and log.
- `runnrr update <ID> [options]`: Mutate ticket content.
    - `--goal TEXT`: Update goal.
    - `--notes TEXT`: Update notes.
    - `--add-task TEXT`: Add a task.
    - `--check-task INDEX`: Mark task done (0-based).
    - `--uncheck-task INDEX`: Mark task undone.
    - `--add-ac TEXT`: Add acceptance criterion.
    - `--check-ac INDEX`: Mark AC done.
    - `--uncheck-ac INDEX`: Mark AC undone.
    - `--tag TAG`: Set tags (repeatable).
- `runnrr start <ID>`: Move ticket to `in-progress`.
- `runnrr done <ID>`: Complete ticket (fails if ACs are incomplete).
- `runnrr block <ID> <REASON>`: Move ticket to `blocked`.
- `runnrr log <ID> <MESSAGE>`: Append a progress entry to the ticket log.

### Epic Management
- `runnrr epic create <TITLE> [--type TYPE] [--priority PRIO] [--goal TEXT] [--tag TAG]`: Create an epic.
- `runnrr epic list [--tag TAG]`: View all epics and their computed status/progress.
- `runnrr epic describe <ID>`: View epic details and child tickets.
- `runnrr epic update <ID> [options]`:
    - `--title TEXT`: Update title.
    - `--goal TEXT`: Update goal.
    - `--notes TEXT`: Update notes.
    - `--metric TEXT`: Set success metrics (repeatable).
    - `--tag TAG`: Set tags.

### Architecture Decision Records (ADRs)
- `runnrr adr create <TITLE> --context TEXT --decision TEXT [--consequences TEXT] [--alternatives TEXT] [--supersedes ID] [--ticket ID] [--epic ID] [--tag TAG]`: Author a new ADR.
- `runnrr adr list [--status STATUS] [--tag TAG]`: View ADRs.
- `runnrr adr describe <ID>`: View full ADR content and history.
- `runnrr adr accept <ID>`: Finalize a `proposed` ADR.
- `runnrr adr update <ID> [options]`:
    - `--title TEXT`, `--context TEXT`, `--decision TEXT`, `--consequences TEXT`, `--alternatives TEXT`, `--tag TAG`.

### Knowledge & Search
- `runnrr context <ID> [--budget N]`: Retrieve token-budgeted context for a ticket.
- `runnrr search <QUERY>`: Full-text search across all entities.
- `runnrr find-related <ID>`: Find entities related by tags or links.
- `runnrr link <SRC> <TARGET>`: Bidirectionally link any two entities.
- `runnrr index rebuild`: Force a rebuild of the FTS5 search index.

## Python SDK

```python
from runnrr import RunnrrClient

client = RunnrrClient()
ticket = client.create_ticket("Implement feature", tags=["core"])
client.transition(ticket.id, "in-progress")
client.check_ticket_ac(ticket.id, 0)
```

## License

MIT
