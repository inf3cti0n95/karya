# Karya

Karya is a deterministic, file-based execution system for autonomous agents. It is not a task tracker; it is a protocol and local-first engine that stores all state in the filesystem, provides a human-first CLI with JSON support, and exposes a Python SDK.

## Key Principles

- **Filesystem is the State**: A ticket's folder is its source of truth. No DB required.
- **Deterministic Workflows**: Explicit state machine transitions and validation rules.
- **Bidirectional Traceability**: Links between tickets, epics, and ADRs are automatically maintained.
- **Git Integration**: Every mutation triggers a structured commit for a perfect audit trail.
- **Searchable Knowledge**: SQLite FTS5 search and tag-based discovery across all entities.

## Installation

```bash
uv pip install -e ".[dev]"
```

## Core Entities

### Tickets
The atomic unit of work. Contains tasks, acceptance criteria, and an execution log.
- `karya create "My first ticket"`

### Epics
Strategic groupings of tickets. Status is derived from child ticket states.
- `karya epic create "Auth System"`

### ADRs (Architecture Decision Records)
Append-only, immutable records of technical decisions. Once `accepted`, they are frozen.
- `karya adr create "Use JWT"`

## Advanced Features

### Scoped Context
The `karya exec` command builds a dynamic context bundle for an agent, injecting only the relevant ADRs, epics, and conventions based on the ticket's tags.

### Tag Infrastructure
Unified tag normalization and searching.
- `karya search "auth" --type adr`
- `karya find-related TICKET-007`

### Linking
Explicitly manage relationships between entities.
- `karya link ticket TICKET-001 epic EPIC-001`
- `karya links TICKET-001`

## Python SDK

```python
from karya import KaryaClient

client = KaryaClient(root=".", agent="backend-agent")
ticket = client.create_ticket("Build auth middleware", labels=["auth"])
client.link("ticket", ticket.id, "epic", "EPIC-001")
client.transition(ticket.id, "in-progress")
```

## Directory layout

```
.karya/
	tickets/            ← State-segregated folders
	epics/              ← Epic entities
	adrs/               ← Architecture Decision Records
	context/            ← Static conventions and glossaries
	events/             ← Append-only JSONL event logs
	sprints/            ← Sprint definitions
	.index/             ← SQLite FTS5 index (gitignored)
```

## Development

Run tests:

```bash
uv run pytest
```

## License

MIT
