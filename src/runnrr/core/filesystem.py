"""Filesystem operations for Runnrr."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

import frontmatter

RUNNRR_ROOT = ".runnrr"

TICKET_DIRS: Dict[str, Path] = {
	"backlog": Path(RUNNRR_ROOT) / "tickets" / "backlog",
	"todo": Path(RUNNRR_ROOT) / "tickets" / "todo",
	"in-progress": Path(RUNNRR_ROOT) / "tickets" / "in-progress",
	"blocked": Path(RUNNRR_ROOT) / "tickets" / "blocked",
	"done": Path(RUNNRR_ROOT) / "tickets" / "done",
}

CONTEXT_DIR = Path(RUNNRR_ROOT) / "context"
EPICS_DIR = Path(RUNNRR_ROOT) / "epics"
ADRS_DIR = Path(RUNNRR_ROOT) / "adrs"

_TICKET_ID_RE = re.compile(r"TICKET-(\d+)")
_EPIC_ID_RE = re.compile(r"EPIC-(\d+)")
_ADR_ID_RE = re.compile(r"ADR-(\d+)")


def normalize_root(root: Path) -> Path:
	if root.name == RUNNRR_ROOT:
		return root.parent
	return root


def init_runnrr(root: Path) -> None:
	"""Create the minimal .runnrr directory tree."""
	(root / RUNNRR_ROOT).mkdir(parents=True, exist_ok=True)

	for path in TICKET_DIRS.values():
		(root / path).mkdir(parents=True, exist_ok=True)

	for path in [CONTEXT_DIR, EPICS_DIR, ADRS_DIR]:
		(root / path).mkdir(parents=True, exist_ok=True)

	_write_if_missing(
		root / CONTEXT_DIR / "conventions.md",
		"""# Conventions

All APIs: {data, error, meta} envelope.
Commits: feat(scope): message
""",
	)


def find_ticket_path(ticket_id: str, root: Path) -> Path | None:
	for status_dir in TICKET_DIRS.values():
		candidate = root / status_dir / f"{ticket_id}.md"
		if candidate.exists():
			return candidate
	return None


def read_file(path: Path) -> Tuple[dict, str]:
	post = frontmatter.load(path)
	return post.metadata, post.content


def write_file(path: Path, frontmatter_dict: dict, body: str) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	post = frontmatter.Post(body, **frontmatter_dict)
	path.write_text(frontmatter.dumps(post), encoding="utf-8")


def move_ticket(current_path: Path, new_status: str, root: Path) -> Path:
	if new_status not in TICKET_DIRS:
		raise ValueError(f"Unknown status '{new_status}'.")

	destination_dir = root / TICKET_DIRS[new_status]
	destination_dir.mkdir(parents=True, exist_ok=True)
	destination = destination_dir / current_path.name
	current_path.replace(destination)
	return destination


def list_tickets_in_state(status: str, root: Path) -> List[Path]:
	if status not in TICKET_DIRS:
		raise ValueError(f"Unknown status '{status}'.")

	status_dir = root / TICKET_DIRS[status]
	if not status_dir.exists():
		return []

	return sorted(status_dir.glob("*.md"))


def generate_id(entity_type: str, root: Path) -> str:
	if entity_type == "ticket":
		pattern = _TICKET_ID_RE
		prefix = "TICKET"
		dirs = [root / d for d in TICKET_DIRS.values()]
	elif entity_type == "epic":
		pattern = _EPIC_ID_RE
		prefix = "EPIC"
		dirs = [root / EPICS_DIR]
	elif entity_type == "adr":
		pattern = _ADR_ID_RE
		prefix = "ADR"
		dirs = [root / ADRS_DIR]
	else:
		raise ValueError(f"Unknown entity type '{entity_type}'")

	max_id = 0
	for d in dirs:
		if not d.exists():
			continue
		for path in d.glob(f"{prefix}-*.md"):
			match = pattern.match(path.stem)
			if match:
				max_id = max(max_id, int(match.group(1)))

	return f"{prefix}-{(max_id + 1):03d}"


def find_epic_path(epic_id: str, root: Path) -> Path | None:
	path = root / EPICS_DIR / f"{epic_id}.md"
	return path if path.exists() else None


def list_all_epics(root: Path) -> List[Path]:
	return sorted((root / EPICS_DIR).glob("EPIC-*.md"))


def find_adr_path(adr_id: str, root: Path) -> Path | None:
	path = root / ADRS_DIR / f"{adr_id}.md"
	return path if path.exists() else None


def list_all_adrs(root: Path) -> List[Path]:
	return sorted((root / ADRS_DIR).glob("ADR-*.md"))


def _write_if_missing(path: Path, content: str) -> None:
	if path.exists():
		return
	path.write_text(content, encoding="utf-8")
