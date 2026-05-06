"""Markdown ticket parser and serializer."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List

import frontmatter

from karya.core.models import (
	ADR,
	ADRStatus,
	Epic,
	EpicStatus,
	EpicType,
	Priority,
	Ticket,
	TicketStatus,
	TicketType,
)

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

_EPIC_SECTIONS = [
	"🎯 Goal",
	"🧠 Context",
	"✅ Success Metrics",
	"📝 Notes",
]

_ADR_SECTIONS = [
	"Context",
	"Decision",
	"Consequences",
	"Alternatives Considered",
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


def parse_epic(path: Path) -> Epic:
	post = frontmatter.load(path)
	sections = _split_sections(post.content)
	frontmatter_data = _coerce_epic_frontmatter(post.metadata)

	epic = Epic(**frontmatter_data)
	epic.goal_text = sections.get("🎯 Goal") or sections.get("Goal") or None
	epic.context_text = sections.get("🧠 Context") or sections.get("Context") or None

	metrics_section = sections.get("✅ Success Metrics") or sections.get("Success Metrics") or ""
	epic.success_metrics = _parse_bullets(metrics_section)

	epic.path = path
	return epic


def serialize_epic(epic: Epic) -> str:
	epic.updated_at = datetime.now(timezone.utc)
	frontmatter_dict = epic.model_dump(
		exclude={
			"goal_text",
			"context_text",
			"success_metrics",
			"status",
			"progress",
			"path",
		},
		mode="json",
	)

	if epic.status == EpicStatus.ARCHIVED:
		frontmatter_dict["status"] = EpicStatus.ARCHIVED.value

	sections: list[str] = []
	content_map = {
		"🎯 Goal": epic.goal_text or "",
		"🧠 Context": epic.context_text or "",
		"✅ Success Metrics": _format_bullets(epic.success_metrics),
		"📝 Notes": "",
	}

	for header in _EPIC_SECTIONS:
		sections.append(f"## {header}\n\n{content_map.get(header, "").strip()}\n")

	body = "\n".join(sections).strip() + "\n"
	post = frontmatter.Post(body, **frontmatter_dict)
	return frontmatter.dumps(post)


def parse_adr(path: Path) -> ADR:
	post = frontmatter.load(path)
	sections = _split_sections(post.content)
	frontmatter_data = _coerce_adr_frontmatter(post.metadata)

	adr = ADR(**frontmatter_data)
	adr.context_text = sections.get("Context") or None
	adr.decision_text = sections.get("Decision") or None
	adr.consequences_text = sections.get("Consequences") or None
	adr.alternatives_text = (
		sections.get("Alternatives Considered") or sections.get("Alternatives") or None
	)

	adr.path = path
	return adr


def serialize_adr(adr: ADR) -> str:
	frontmatter_dict = adr.model_dump(
		exclude={
			"context_text",
			"decision_text",
			"consequences_text",
			"alternatives_text",
			"path",
		},
		mode="json",
	)

	sections: list[str] = []
	content_map = {
		"Context": adr.context_text or "",
		"Decision": adr.decision_text or "",
		"Consequences": adr.consequences_text or "",
		"Alternatives Considered": adr.alternatives_text or "",
	}

	for header in _ADR_SECTIONS:
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


def _coerce_epic_frontmatter(frontmatter_data: dict) -> dict:
	data = dict(frontmatter_data)

	epic_type = data.get("type")
	if isinstance(epic_type, str):
		data["type"] = EpicType(epic_type)

	priority = data.get("priority")
	if isinstance(priority, str):
		data["priority"] = Priority(priority)

	status = data.get("status")
	if isinstance(status, str):
		data["status"] = EpicStatus(status)

	for field in ("created_at", "updated_at"):
		value = data.get(field)
		if isinstance(value, str):
			data[field] = _parse_datetime(value)

	return data


def _coerce_adr_frontmatter(frontmatter_data: dict) -> dict:
	data = dict(frontmatter_data)

	status = data.get("status")
	if isinstance(status, str):
		data["status"] = ADRStatus(status)

	for field in ("date",):
		value = data.get(field)
		if isinstance(value, str):
			data[field] = date.fromisoformat(value)

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


def _parse_bullets(section: str) -> list[str]:
	items: list[str] = []
	for line in section.splitlines():
		line = line.strip()
		if line.startswith("- "):
			items.append(line[2:].strip())
	return items


def _format_bullets(items: list[str]) -> str:
	return "\n".join([f"- {item}" for item in items])
