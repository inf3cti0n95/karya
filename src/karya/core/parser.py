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

_TICKET_SECTIONS = [
	"Goal",
	"Tasks",
	"Acceptance Criteria",
	"Log",
	"Notes",
]

_EPIC_SECTIONS = [
	"Goal",
	"Success Metrics",
	"Notes",
]

_ADR_SECTIONS = [
	"Context",
	"Decision",
	"Consequences",
	"Alternatives",
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


def _parse_bullets(section: str) -> list[str]:
	items: list[str] = []
	for line in section.splitlines():
		line = line.strip()
		if line.startswith("- "):
			items.append(line[2:].strip())
	return items


def _format_bullets(items: list[str]) -> str:
	return "\n".join([f"- {item}" for item in items])


def _format_checkbox_section(items: list[dict]) -> str:
	lines: list[str] = []
	for item in items:
		done = "x" if item.get("done") else " "
		text = item.get("text", "")
		lines.append(f"- [{done}] {text}")
	return "\n".join(lines)


def parse_ticket(path: Path) -> Ticket:
	post = frontmatter.load(path)
	sections = _split_sections(post.content)

	metadata = dict(post.metadata)
	if "status" in metadata:
		metadata["status"] = TicketStatus(metadata["status"])
	if "type" in metadata:
		metadata["type"] = TicketType(metadata["type"])
	if "priority" in metadata:
		metadata["priority"] = Priority(metadata["priority"])
	for field in ("created_at", "updated_at"):
		if isinstance(metadata.get(field), str):
			metadata[field] = datetime.fromisoformat(metadata[field].replace("Z", "+00:00"))

	ticket = Ticket(**metadata)
	ticket.goal_text = sections.get("Goal") or None
	ticket.tasks = _parse_checkbox_section(sections.get("Tasks", ""))
	ticket.acceptance_criteria = _parse_checkbox_section(sections.get("Acceptance Criteria", ""))
	ticket.execution_log = _parse_log_section(sections.get("Log", ""))
	ticket.notes_text = sections.get("Notes") or None
	ticket.path = path
	return ticket


def serialize_ticket(ticket: Ticket) -> str:
	ticket.updated_at = datetime.now(timezone.utc)
	frontmatter_dict = ticket.model_dump(
		exclude={
			"goal_text",
			"tasks",
			"acceptance_criteria",
			"execution_log",
			"notes_text",
			"path",
		},
		mode="json",
	)

	content_map = {
		"Goal": ticket.goal_text or "",
		"Tasks": _format_checkbox_section(ticket.tasks),
		"Acceptance Criteria": _format_checkbox_section(ticket.acceptance_criteria),
		"Log": _format_log_section(ticket.execution_log),
		"Notes": ticket.notes_text or "",
	}

	sections: list[str] = []
	for header in _TICKET_SECTIONS:
		sections.append(f"## {header}\n\n{content_map.get(header, '').strip()}\n")

	body = "\n".join(sections).strip() + "\n"
	post = frontmatter.Post(body, **frontmatter_dict)
	return frontmatter.dumps(post)


def parse_epic(path: Path) -> Epic:
	post = frontmatter.load(path)
	sections = _split_sections(post.content)
	metadata = dict(post.metadata)
	
	if "type" in metadata:
		metadata["type"] = EpicType(metadata["type"])
	if "priority" in metadata:
		metadata["priority"] = Priority(metadata["priority"])
	for field in ("created_at", "updated_at"):
		if isinstance(metadata.get(field), str):
			metadata[field] = datetime.fromisoformat(metadata[field].replace("Z", "+00:00"))

	epic = Epic(**metadata)
	epic.goal_text = sections.get("Goal") or None
	epic.success_metrics = _parse_bullets(sections.get("Success Metrics", ""))
	epic.notes_text = sections.get("Notes") or None
	epic.path = path
	return epic


def serialize_epic(epic: Epic) -> str:
	epic.updated_at = datetime.now(timezone.utc)
	frontmatter_dict = epic.model_dump(
		exclude={
			"goal_text",
			"success_metrics",
			"notes_text",
			"path",
		},
		mode="json",
	)

	content_map = {
		"Goal": epic.goal_text or "",
		"Success Metrics": _format_bullets(epic.success_metrics),
		"Notes": epic.notes_text or "",
	}

	sections: list[str] = []
	for header in _EPIC_SECTIONS:
		sections.append(f"## {header}\n\n{content_map.get(header, '').strip()}\n")

	body = "\n".join(sections).strip() + "\n"
	post = frontmatter.Post(body, **frontmatter_dict)
	return frontmatter.dumps(post)


def parse_adr(path: Path) -> ADR:
	post = frontmatter.load(path)
	sections = _split_sections(post.content)
	metadata = dict(post.metadata)

	if "status" in metadata:
		metadata["status"] = ADRStatus(metadata["status"])
	if isinstance(metadata.get("date"), str):
		metadata["date"] = date.fromisoformat(metadata["date"])

	adr = ADR(**metadata)
	adr.context_text = sections.get("Context") or None
	adr.decision_text = sections.get("Decision") or None
	adr.consequences_text = sections.get("Consequences") or None
	adr.alternatives_text = sections.get("Alternatives") or None
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

	content_map = {
		"Context": adr.context_text or "",
		"Decision": adr.decision_text or "",
		"Consequences": adr.consequences_text or "",
		"Alternatives": adr.alternatives_text or "",
	}

	sections: list[str] = []
	for header in _ADR_SECTIONS:
		sections.append(f"## {header}\n\n{content_map.get(header, '').strip()}\n")

	body = "\n".join(sections).strip() + "\n"
	post = frontmatter.Post(body, **frontmatter_dict)
	return frontmatter.dumps(post)


def _parse_log_section(section: str) -> list[dict]:
	# Format: [2026-05-04T11:20Z] Message
	entries = []
	pattern = re.compile(r"^\[(.*?)\] (.*)$")
	for line in section.splitlines():
		match = pattern.match(line.strip())
		if match:
			entries.append({"timestamp": match.group(1), "message": match.group(2)})
	return entries


def _format_log_section(entries: list[dict]) -> str:
	lines = []
	for entry in entries:
		lines.append(f"[{entry.get('timestamp')}] {entry.get('message')}")
	return "\n".join(lines)
