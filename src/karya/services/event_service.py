"""Event log append-only service."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from karya.core.filesystem import EVENTS_DIR, append_event, normalize_root
from karya.core.models import Event


class EventService:
	def __init__(self, root: Path):
		self.root = normalize_root(root)

	def emit(self, event: Event) -> None:
		append_event(event, self.root)

	def list(self, ticket_id: str | None = None, last: int = 20) -> list[Event]:
		events_dir = self.root / EVENTS_DIR
		if not events_dir.exists():
			return []

		events: list[Event] = []
		for path in sorted(events_dir.glob("*.jsonl")):
			for line in path.read_text(encoding="utf-8").splitlines():
				if not line.strip():
					continue
				payload = json.loads(line)
				if ticket_id and payload.get("ticket_id") != ticket_id:
					continue
				payload = _coerce_event_payload(payload)
				events.append(Event(**payload))

		if last <= 0:
			return []

		return list(reversed(events[-last:]))


def _coerce_event_payload(payload: dict) -> dict:
	data = dict(payload)
	timestamp = data.get("timestamp")
	if isinstance(timestamp, str):
		data["timestamp"] = _parse_datetime(timestamp)
	return data


def _parse_datetime(value: str) -> datetime:
	normalized = value.replace("Z", "+00:00")
	return datetime.fromisoformat(normalized)
