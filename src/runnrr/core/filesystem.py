"""Filesystem operations for Runnrr."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

from runnrr.exceptions import RunnrrNotInitializedError

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


def find_runnrr_root(start: Path = Path(".")) -> Path:
	"""
	Walk UP from start until .runnrr/ is found.
	Raises RunnrrNotInitializedError if not found.
	"""
	current = start.resolve()
	while True:
		candidate = current / RUNNRR_ROOT
		if candidate.exists() and candidate.is_dir():
			return current
		
		parent = current.parent
		if parent == current:
			raise RunnrrNotInitializedError(
				"No .runnrr/ directory found. Run `runnrr init` first."
			)
		current = parent


def init_runnrr(root: Path) -> None:
	"""Create the minimal .runnrr directory tree and ensure git isolation."""
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

	# Git isolation
	host_gitignore = find_host_gitignore(Path.cwd())
	if host_gitignore:
		_ensure_gitignore_entry(host_gitignore, f"{RUNNRR_ROOT}/")


def find_host_gitignore(start: Path) -> Path | None:
	"""
	Walk up directory tree from `start`. Return path to .gitignore if a .git/ directory is found at the same level.
	Return None if we hit the filesystem root without finding .git/.
	"""
	current = start.resolve()
	while True:
		git_dir = current / ".git"
		if git_dir.exists() and git_dir.is_dir():
			return current / ".gitignore"
		
		parent = current.parent
		if parent == current:
			return None
		current = parent


def _ensure_gitignore_entry(gitignore_path: Path, entry: str) -> None:
	"""
	Add `entry` to .gitignore if not already present. Creates the file if it doesn't exist.
	Appends with a newline. Does not modify existing content.
	"""
	if gitignore_path.exists():
		existing = gitignore_path.read_text(encoding="utf-8")
		if entry in existing.splitlines():
			return
		
		# Append, ensuring there's a trailing newline before our entry
		if existing and not existing.endswith("\n"):
			gitignore_path.write_text(existing + "\n" + entry + "\n", encoding="utf-8")
		else:
			gitignore_path.write_text(existing + entry + "\n", encoding="utf-8")
	else:
		gitignore_path.write_text(entry + "\n", encoding="utf-8")


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


def archive_v01(root: Path) -> Path:
	"""Rename old directories to .runnrr/archive_v01/."""
	archive_dir = root / RUNNRR_ROOT / "archive_v01"
	archive_dir.mkdir(parents=True, exist_ok=True)

	for d in ["tickets", "epics", "adrs"]:
		old_dir = root / RUNNRR_ROOT / d
		if old_dir.exists():
			new_dir = archive_dir / d
			old_dir.rename(new_dir)
	
	return archive_dir


def export_ticket_md(ticket: 'Ticket') -> str:
	from runnrr.core.parser import serialize_ticket
	return serialize_ticket(ticket)


def export_epic_md(epic: 'Epic') -> str:
	from runnrr.core.parser import serialize_epic
	return serialize_epic(epic)


def export_adr_md(adr: 'ADR') -> str:
	from runnrr.core.parser import serialize_adr
	return serialize_adr(adr)


def _write_if_missing(path: Path, content: str) -> None:
	if path.exists():
		return
	path.write_text(content, encoding="utf-8")
