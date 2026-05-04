"""Filesystem operations for Karya."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import frontmatter

from karya.core.models import Event

KARYA_ROOT = ".karya"

TICKET_DIRS: Dict[str, Path] = {
	"backlog": Path(KARYA_ROOT) / "tickets" / "backlog",
	"todo": Path(KARYA_ROOT) / "tickets" / "todo",
	"in-progress": Path(KARYA_ROOT) / "tickets" / "in-progress",
	"blocked": Path(KARYA_ROOT) / "tickets" / "blocked",
	"done": Path(KARYA_ROOT) / "tickets" / "done",
}

CONTEXT_DIR = Path(KARYA_ROOT) / "context"
AGENTS_DIR = Path(KARYA_ROOT) / "agents"
EPICS_DIR = Path(KARYA_ROOT) / "epics"
SPRINTS_DIR = Path(KARYA_ROOT) / "sprints"
EVENTS_DIR = Path(KARYA_ROOT) / "events"
LOGS_DIR = Path(KARYA_ROOT) / "logs"
SCHEMAS_DIR = Path(KARYA_ROOT) / "schemas"

_TICKET_ID_RE = re.compile(r"TICKET-(\d+)")


def normalize_root(root: Path) -> Path:
	if root.name == KARYA_ROOT:
		return root.parent
	return root


def init_karya(root: Path) -> None:
	"""Create the full .karya directory tree if it doesn't exist."""
	root_path = root / KARYA_ROOT
	root_path.mkdir(parents=True, exist_ok=True)

	for path in TICKET_DIRS.values():
		(root / path).mkdir(parents=True, exist_ok=True)

	for path in [
		CONTEXT_DIR,
		AGENTS_DIR,
		EPICS_DIR,
		SPRINTS_DIR,
		EVENTS_DIR,
		LOGS_DIR,
		SCHEMAS_DIR,
	]:
		(root / path).mkdir(parents=True, exist_ok=True)

	_write_if_missing(
		root / CONTEXT_DIR / "architecture.md",
		"""# System Architecture

> Update this file as your architecture evolves.

## Overview
Describe your system here.

## Services
- List your services

## Data Flow
- Describe how data moves
""",
	)
	_write_if_missing(
		root / CONTEXT_DIR / "conventions.md",
		"""# Conventions

## Git Commits
Follow conventional commits: feat:, fix:, chore:, docs:

## Naming
- Files: kebab-case
- Functions: snake_case
- Classes: PascalCase
""",
	)
	_write_if_missing(
		root / AGENTS_DIR / "agents.yaml",
		"""agents:
  default-agent:
    description: "General purpose agent"
    skills: []
    max_concurrent_tickets: 1
""",
	)


def find_ticket_path(ticket_id: str, root: Path) -> Path | None:
	"""Search all status folders for a ticket by ID. Returns Path or None."""
	for status_dir in TICKET_DIRS.values():
		candidate = root / status_dir / f"{ticket_id}.md"
		if candidate.exists():
			return candidate
	return None


def read_ticket_file(path: Path) -> Tuple[dict, str]:
	"""Read a .md file. Returns (frontmatter_dict, body_str)."""
	post = frontmatter.load(path)
	return post.metadata, post.content


def write_ticket_file(path: Path, frontmatter_dict: dict, body: str) -> None:
	"""Write frontmatter + body to disk atomically."""
	path.parent.mkdir(parents=True, exist_ok=True)
	tmp_path = path.with_suffix(path.suffix + ".tmp")
	post = frontmatter.Post(body, **frontmatter_dict)

	with tmp_path.open("wb") as handle:
		frontmatter.dump(post, handle)

	tmp_path.replace(path)


def move_ticket(current_path: Path, new_status: str, root: Path) -> Path:
	"""Move a ticket file to the correct status folder."""
	if new_status not in TICKET_DIRS:
		raise ValueError(f"Unknown status '{new_status}'.")

	destination_dir = root / TICKET_DIRS[new_status]
	destination_dir.mkdir(parents=True, exist_ok=True)
	destination = destination_dir / current_path.name
	current_path.replace(destination)
	return destination


def list_tickets_in_state(status: str, root: Path) -> List[Path]:
	"""Return all .md paths in a given status folder."""
	if status not in TICKET_DIRS:
		raise ValueError(f"Unknown status '{status}'.")

	status_dir = root / TICKET_DIRS[status]
	if not status_dir.exists():
		return []

	return sorted(status_dir.glob("*.md"))


def generate_ticket_id(root: Path) -> str:
	"""Auto-increment ticket IDs across all status folders."""
	max_id = 0
	for status_dir in TICKET_DIRS.values():
		for path in (root / status_dir).glob("*.md"):
			match = _TICKET_ID_RE.match(path.stem)
			if match:
				value = int(match.group(1))
				max_id = max(max_id, value)

	next_id = max_id + 1
	return f"TICKET-{next_id:03d}"


def append_event(event: Event, root: Path) -> None:
	"""Append a JSON line to .karya/events/YYYY-MM-DD.jsonl."""
	events_dir = root / EVENTS_DIR
	events_dir.mkdir(parents=True, exist_ok=True)

	date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
	path = events_dir / f"{date_str}.jsonl"
	payload = event.model_dump(mode="json")

	with path.open("a", encoding="utf-8") as handle:
		handle.write(json.dumps(payload) + "\n")


def load_context_files(root: Path) -> str:
	"""Read all .md files in .karya/context/ and return merged string."""
	context_dir = root / CONTEXT_DIR
	if not context_dir.exists():
		return ""

	parts: list[str] = []
	for path in sorted(context_dir.glob("*.md")):
		content = path.read_text(encoding="utf-8")
		parts.append(f"# {path.name}\n{content}\n\n---\n\n")

	return "".join(parts)


def _write_if_missing(path: Path, content: str) -> None:
	if path.exists():
		return
	path.write_text(content, encoding="utf-8")
