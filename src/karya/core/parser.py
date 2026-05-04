"""Markdown ticket parser and serializer."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import frontmatter

from karya.core.models import Priority, Ticket, TicketStatus, TicketType

_SECTION_HEADER = re.compile(r"^##\s+(.*)$")
_CHECKBOX = re.compile(r"^- \[( |x|X)\] (.+)$")
_EXECUTION_LOG = re.compile(r"<!--\s*(\[[\s\S]*?\])\s*-->")

_ORDERED_SECTIONS = [
	"Context",
	"Goal",
	"Scope",
	"🪜 Tasks",
	"🧪 Acceptance Criteria",
	"📜 Execution Log",
	"🧭 Agent Instructions",
]


def _split_sections(body: str) -> Dict[str, str]:
	sections: Dict[str, List[str]] = {}
	current_header: str | None = None

	for line in body.splitlines():
		header_match = _SECTION_HEADER.match(line)
		if header_match:
			current_header = header_match.group(1).strip()
			sections.setdefault(current_header, [])
			continue

		if current_header is None:
			continue

		sections[current_header].append(line)

	return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def _parse_checkbox_section(section: str) -> list[dict]:
	items: list[dict] = []
	for line in section.splitlines():
		match = _CHECKBOX.match(line.strip())
		if not match:
			continue
		done = match.group(1).lower() == "x"
		items.append({"text": match.group(2).strip(), "done": done})
	return items


def _parse_execution_log(section: str) -> list[dict]:
	match = _EXECUTION_LOG.search(section)
	if not match:
		return []
	try:
		data = json.loads(match.group(1))
	except json.JSONDecodeError:
		return []
	return data if isinstance(data, list) else []


def parse_ticket(path: Path) -> Ticket:
	post = frontmatter.load(path)
	sections = _split_sections(post.content)

	frontmatter_data = _coerce_frontmatter(post.metadata)
	ticket = Ticket(**frontmatter_data)
	ticket.context_text = sections.get("Context") or None
	ticket.goal_text = sections.get("Goal") or None
	ticket.scope_text = sections.get("Scope") or None

	tasks_section = sections.get("🪜 Tasks", "")
	acceptance_section = sections.get("🧪 Acceptance Criteria", "")
	execution_section = sections.get("📜 Execution Log", "")

	ticket.tasks = _parse_checkbox_section(tasks_section)
	ticket.acceptance_criteria = _parse_checkbox_section(acceptance_section)
	ticket.execution_log = _parse_execution_log(execution_section)

	agent_instructions = sections.get("🧭 Agent Instructions") or sections.get(
		"Agent Instructions"
	)
	ticket.agent_instructions = agent_instructions or None
	ticket.path = path
	return ticket


def serialize_ticket(ticket: Ticket) -> str:
	ticket.updated_at = datetime.now(timezone.utc)

	frontmatter_dict = ticket.model_dump(
		exclude={
			"context_text",
			"goal_text",
			"scope_text",
			"tasks",
			"acceptance_criteria",
			"execution_log",
			"agent_instructions",
			"path",
		},
		mode="json",
	)

	sections: list[str] = []
	context = ticket.context_text or ""
	goal = ticket.goal_text or ""
	scope = ticket.scope_text or ""
	tasks = _format_checkbox_section(ticket.tasks)
	acceptance = _format_checkbox_section(ticket.acceptance_criteria)
	execution = _format_execution_log(ticket.execution_log)
	instructions = ticket.agent_instructions or ""

	content_map = {
		"Context": context,
		"Goal": goal,
		"Scope": scope,
		"🪜 Tasks": tasks,
		"🧪 Acceptance Criteria": acceptance,
		"📜 Execution Log": execution,
		"🧭 Agent Instructions": instructions,
	}

	for header in _ORDERED_SECTIONS:
		sections.append(f"## {header}\n\n{content_map.get(header, "").strip()}\n")

	body = "\n".join(sections).strip() + "\n"
	post = frontmatter.Post(body, **frontmatter_dict)
	return frontmatter.dumps(post)


def _coerce_frontmatter(frontmatter_data: dict) -> dict:
	data = dict(frontmatter_data)

	status = data.get("status")
	if isinstance(status, str):
		data["status"] = TicketStatus(status)

	ticket_type = data.get("type")
	if isinstance(ticket_type, str):
		data["type"] = TicketType(ticket_type)

	priority = data.get("priority")
	if isinstance(priority, str):
		data["priority"] = Priority(priority)

	for field in ("created_at", "updated_at"):
		value = data.get(field)
		if isinstance(value, str):
			data[field] = _parse_datetime(value)

	return data


def _parse_datetime(value: str) -> datetime:
	normalized = value.replace("Z", "+00:00")
	return datetime.fromisoformat(normalized)


def _format_checkbox_section(items: list[dict]) -> str:
	lines: list[str] = []
	for item in items:
		done = "x" if item.get("done") else " "
		text = item.get("text", "")
		lines.append(f"- [{done}] {text}")
	return "\n".join(lines)


def _format_execution_log(items: list[dict]) -> str:
	payload = json.dumps(items, separators=(",", ":"), default=str)
	return f"<!-- {payload} -->"
