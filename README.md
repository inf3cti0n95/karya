# Runnrr

```
Git for agent workspaces.
```

Runnrr is a filesystem-native, markdown-based workspace protocol that gives coding agents (and humans) durable structured state, explicit task boundaries, and lightweight context retrieval. 

It is **not** an autonomous loop runtime, a checkpoint engine, a multi-agent orchestrator, or a sprawling platform. It is simply the structured workspace that tools like Gemini CLI and Claude Code work inside to understand what to do next.

## The Five Commands That Matter

```bash
runnrr next        # what should I work on?
runnrr context     # what do I need to know?
runnrr log         # what did I just do?
runnrr done        # I finished this
runnrr adr         # I made an architectural decision
```

Everything else is in service of these five.

## The Stack

```
.runnrr/              Filesystem. Source of truth. Always.
├── tickets/         Markdown files. Folder = state.
├── epics/           Markdown files.
├── adrs/            Markdown files.
└── context/         conventions.md, glossary.md. Static. Human-maintained.

.runnrr/.db           SQLite. Derived only. Gitignored.
                     Rebuilt anytime with: runnrr index rebuild
                     Used for: search, next-ticket ranking, context scoring
```

**Rule:** If `.db` is deleted, everything still works. It just gets slow. The markdown files are always the absolute source of truth.

## Core Entities

### Tickets
The atomic unit of work. Status is determined by which folder the markdown file lives in (`backlog`, `todo`, `in-progress`, `blocked`, `done`). 
- `runnrr create "My first ticket"`

### Epics
Strategic groupings of tickets. Status is strictly computed from child ticket states. Never stored manually.
- `runnrr epic create "Auth System"`

### ADRs (Architecture Decision Records)
Append-only, immutable records of technical decisions. Once `accepted`, they are frozen.
- `runnrr adr create "Use JWT" --context "..." --decision "..."`

## The Agent Workflow

Runnrr shines when used alongside an LLM CLI. 

### 1. Initialization and Context
The agent runs `runnrr exec` at the start of a session. This command automatically:
- Calls `runnrr next` to find the highest priority unblocked ticket.
- Calls `runnrr context` to dynamically assemble a token-budgeted, relevance-ranked context payload (including the ticket, blockers, Epics, related ADRs, and project conventions).
- Calculates the valid state machine actions the agent is allowed to take.

### 2. Execution
The agent starts the work via the CLI:
```bash
runnrr start TICKET-001
```

As the agent writes code, it logs progress directly into the ticket via the CLI to maintain a perfect audit trail:
```bash
runnrr log TICKET-001 "Provisioned local Elasticsearch container via Docker Compose."
```

### 3. Content Modification (Markdown Direct Editing)
Runnrr relies on **direct file edits** for human-readable content. To mark a task or an acceptance criterion as complete, the agent opens the `.runnrr/tickets/<status>/<TICKET-001>.md` file in their editor and changes `- [ ]` to `- [x]`.

### 4. Completion
Once all acceptance criteria are checked off in the markdown file, the agent completes the work via the CLI:
```bash
runnrr done TICKET-001
```
(If any criteria are unchecked, the CLI parses the file and rejects the transition).

## Python SDK

```python
from runnrr import RunnrrClient

client = RunnrrClient(root=".")
ticket = client.create_ticket("Build auth middleware", tags=["auth"])
client.link(ticket.id, "EPIC-001")
client.transition(ticket.id, "in-progress")
```

## Development

Run tests:

```bash
uv run pytest
```

## License

MIT
