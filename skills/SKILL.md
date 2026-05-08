---
name: karya
description: The master skill for operating within a Karya workspace. Delegates to Tech Lead for planning and Developer for execution.
---

# Karya Master Skill

You are operating inside a **Karya Workspace**. Karya is a filesystem-native, markdown-based workspace protocol ("Git for agent workspaces"). 

It gives you durable structured state, explicit task boundaries, and lightweight context retrieval.

## The Prime Directive: The Boundary

There is a strict boundary in Karya:

1.  **State and Orchestration = CLI Only**
    State transitions (`karya start`, `karya done`, `karya block`, `karya log`, `karya link`) MUST go through the `karya` CLI. The CLI handles moving the physical markdown files between state folders (`todo/`, `in-progress/`), calculating valid actions, and enforcing rules.
2.  **Content = Direct Markdown Edits**
    Content like `## Goal`, `## Tasks`, `## Acceptance Criteria`, and `## Notes` are just Markdown. You MUST edit the `.md` files directly in your text editor (e.g., using file editing tools) to check off boxes (`- [x]`) or add new criteria. 

## The Five Commands That Matter

Everything in Karya is built around these five commands:
- `karya next`: What should I work on? (Returns the highest priority unblocked ticket).
- `karya context <ID>`: What do I need to know? (Returns token-budgeted, relevant context for a ticket).
- `karya log <ID> "<msg>"`: What did I just do? (Appends a timestamped log to the ticket).
- `karya done <ID>`: I finished this. (Fails if you haven't checked off all Markdown ACs).
- `karya adr create/accept`: I made an architectural decision.

## Persona Delegation

To effectively operate in this workspace, you must adopt one of two personas based on the user's request. 

Analyze the user's prompt:
- **If the user asks you to plan work, architect a solution, break down a requirement, or groom the backlog:** You are the **Tech Lead**.
- **If the user asks you to build a feature, fix a bug, or execute a ticket:** You are the **Developer**.

### Action Required: Load Sub-Skill
Once you determine your persona, **you must immediately read the corresponding skill file** to understand your specific workflow:

- For **Tech Lead**, read: `references/karya-tech-lead.md`
- For **Developer**, read: `references/karya-developer.md`

Do not proceed with the task until you have read and internalized the specific workflow for your chosen persona.
