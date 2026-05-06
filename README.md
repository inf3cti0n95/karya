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

## Agent Execution Example: Building a Search Feature

Karya shines when used alongside an LLM CLI (like `gemini-cli` or `claude-code`). Here is a sample scenario where a user asks their AI assistant to "build a search feature for our e-commerce website."

### 1. The Tech Lead Agent (Planning & Architecture)

The user assigns the task to the Tech Lead agent:
> **User**: "Plan the work to build a search feature for the e-commerce site."

The Tech Lead agent acts as the brain, researching and setting up the work:

```bash
# 1. Check for existing context
karya search "search engine"

# 2. Create an Epic for the initiative
karya epic create "Product Search" --type feature --priority high \
  --goal "Allow users to search products by name and category"

# 3. Create an Architecture Decision Record (ADR)
karya adr create "Use Elasticsearch" \
  --context "We need fast, full-text search for the product catalog." \
  --decision "Use Elasticsearch over PostgreSQL full-text search for better scaling and relevance scoring." \
  --tag search --tag database

# 4. Accept the ADR to freeze the decision
karya adr accept ADR-001

# 5. Break down the work into Tickets
karya create "Setup Elasticsearch cluster" --type infra --label search
karya create "Build search API endpoint" --type feature --label search
karya create "Implement search UI components" --type feature --label search --label frontend

# 6. Link tickets to the Epic and ADR
karya link ticket TICKET-001 epic EPIC-001
karya link ticket TICKET-002 epic EPIC-001
karya link ticket TICKET-003 epic EPIC-001
karya link ticket TICKET-001 adr ADR-001
karya link ticket TICKET-002 adr ADR-001

# 7. Move the first ticket to 'todo'
karya start TICKET-001
```

### 2. The Developer Agent (Execution)

The user now invokes the Developer agent to execute the first ticket:
> **User**: "Pick up the next available ticket and execute it."

The Developer agent acts as the muscle, strictly following the defined scope:

```bash
# 1. Find the next ticket in 'todo'
karya next --agent backend-agent
# Returns TICKET-001

# 2. Retrieve scoped context (automatically includes conventions & ADR-001)
karya exec --agent backend-agent
# The agent reads the context bundle, noting that Elasticsearch is required by ADR-001.

# 3. Start work
karya start TICKET-001 --agent backend-agent

# 4. Log progress as code is written
karya log TICKET-001 "Provisioned local Elasticsearch container via Docker Compose."
karya log TICKET-001 "Created basic index mapping for products."

# 5. Mark tasks and acceptance criteria as done
karya update TICKET-001 --field tasks --value '[{"text": "Write docker-compose.yml", "done": true}]'
karya update TICKET-001 --field acceptance_criteria --value '[{"text": "Cluster starts successfully", "done": true}]'

# 6. Complete the ticket
karya done TICKET-001
```

### 3. Handling Tangents

During development, the agent notices a bug in an unrelated authentication middleware. Instead of fixing it and polluting the search feature's scope, the agent follows the **Tangent Protocol**:

```bash
# 1. Log the discovery without breaking flow
karya log TICKET-001 "Spotted missing error handling in auth middleware. Creating a bug ticket."

# 2. Create a separate ticket for the backlog
karya create "Fix auth middleware error handling" --type bug

# 3. Continue working on the search API...
```

This strict separation ensures that Git commits remain atomic, the project history is perfectly auditable, and the context window never overflows with out-of-scope code.

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
