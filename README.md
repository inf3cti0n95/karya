# Karya

Karya is a deterministic, file-based execution system for autonomous agents. It is not a task tracker; it is a protocol and local-first engine that stores all state in the filesystem, provides a human-first CLI with JSON support, and exposes a Python SDK.

## Key principles

- Filesystem is the source of truth. A ticket's folder is its state.
- CLI outputs human-readable tables by default. Use `--json` for automation.
- All writes go through the engine (SDK wraps services, CLI wraps SDK).
- Every mutation triggers a Git commit.
- Every write is schema-validated with Pydantic.

## Installation

```bash
uv pip install -e ".[dev]"
```

## Quick start

Initialize the workspace:

```bash
karya init
```

Create a ticket:

```bash
karya create "My first ticket" --type feature --priority medium
```

List tickets:

```bash
karya list --state backlog
```

Start work:

```bash
karya start TICKET-001 --agent backend-agent
```

Log progress:

```bash
karya log TICKET-001 "Working on it"
```

Attempt to complete (fails until acceptance criteria are checked):

```bash
karya done TICKET-001
```

## Machine Output (JSON)

For agents and automation, use the `--json` flag to receive structured data.

```bash
karya --json list --state todo
```

## Python SDK

```python
from karya import KaryaClient

client = KaryaClient(root=".", agent="backend-agent")
ticket = client.create_ticket("Build auth middleware")
client.transition(ticket.id, "todo")
client.transition(ticket.id, "in-progress")
client.log(ticket.id, "Scaffolded modules")
```

## Directory layout

```
.karya/
	agents/
	context/
	events/
	logs/
	sprints/
	tickets/
		backlog/
		todo/
		in-progress/
		blocked/
		done/
```

## Development

Run tests:

```bash
uv run pytest
```

## License

MIT
