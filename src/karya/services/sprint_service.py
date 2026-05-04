"""Sprint planning operations."""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from karya.core.filesystem import SPRINTS_DIR, append_event, init_karya, normalize_root
from karya.core.models import Event, Priority, Sprint, TicketStatus
from karya.exceptions import SprintNotFoundError
from karya.git.integration import GitIntegration
from karya.services.ticket_service import TicketService

_SPRINT_ID_RE = re.compile(r"sprint-(\d+)")
_PRIORITY_ORDER = {
	Priority.CRITICAL: 0,
	Priority.HIGH: 1,
	Priority.MEDIUM: 2,
	Priority.LOW: 3,
}


class SprintService:
	def __init__(self, root: Path):
		self.root = normalize_root(root)
		self._tickets = TicketService(root)
		self._git = GitIntegration(root)

	def plan(self, limit: int = 5) -> Sprint:
		init_karya(self.root)

		backlog = self._tickets.list(status=TicketStatus.BACKLOG.value)
		eligible = [ticket for ticket in backlog if self._dependencies_done(ticket)]

		eligible.sort(
			key=lambda item: (
				_PRIORITY_ORDER[item.priority],
				item.estimated_effort,
			)
		)
		selected = eligible[:limit]

		sprint_id = _next_sprint_id(self.root)
		today = date.today()
		sprint = Sprint(
			id=sprint_id,
			name=f"Sprint {sprint_id}",
			start_date=today,
			end_date=today + timedelta(days=14),
			tickets=[ticket.id for ticket in selected],
		)

		for ticket in selected:
			self._tickets.transition(ticket.id, TicketStatus.TODO.value)

		path = self.root / SPRINTS_DIR / f"{sprint_id}.yaml"
		_write_sprint(path, sprint)

		append_event(
			Event(event="sprint_planned", data={"sprint_id": sprint_id}),
			self.root,
		)
		self._git.commit(f"{sprint_id} planned ({len(selected)} tickets)")
		return sprint

	def status(self) -> dict:
		sprint = _load_active_sprint(self.root)
		breakdown = {state.value: 0 for state in TicketStatus}

		for ticket_id in sprint.tickets:
			ticket = self._tickets.get(ticket_id)
			breakdown[ticket.status.value] += 1

		return {"sprint": sprint, "breakdown": breakdown}

	def close(self) -> Sprint:
		sprint = _load_active_sprint(self.root)

		incomplete: list[str] = []
		completed = 0
		for ticket_id in sprint.tickets:
			ticket = self._tickets.get(ticket_id)
			if ticket.status == TicketStatus.DONE:
				completed += 1
				continue
			if ticket.status == TicketStatus.IN_PROGRESS:
				incomplete.append(ticket_id)
				self._tickets.log(ticket_id, "Sprint closed with incomplete work.")

		sprint.status = "closed"
		sprint.completed_points = completed

		path = self.root / SPRINTS_DIR / f"{sprint.id}.yaml"
		_write_sprint(path, sprint)

		append_event(
			Event(
				event="sprint_closed",
				data={"sprint_id": sprint.id, "incomplete": incomplete},
			),
			self.root,
		)
		self._git.commit(f"{sprint.id} closed")
		return sprint

	def _dependencies_done(self, ticket) -> bool:
		for dependency in ticket.dependencies:
			dependency_ticket = self._tickets.get(dependency)
			if dependency_ticket.status != TicketStatus.DONE:
				return False
		return True


def _next_sprint_id(root: Path) -> str:
	sprints_dir = root / SPRINTS_DIR
	sprints_dir.mkdir(parents=True, exist_ok=True)
	max_id = 0
	for path in sprints_dir.glob("sprint-*.yaml"):
		match = _SPRINT_ID_RE.match(path.stem)
		if match:
			max_id = max(max_id, int(match.group(1)))
	return f"sprint-{max_id + 1:03d}"


def _load_active_sprint(root: Path) -> Sprint:
	sprints_dir = root / SPRINTS_DIR
	if not sprints_dir.exists():
		raise SprintNotFoundError("No active sprint found.")

	for path in sorted(sprints_dir.glob("sprint-*.yaml")):
		sprint = _read_sprint(path)
		if sprint.status == "active":
			return sprint

	raise SprintNotFoundError("No active sprint found.")


def _write_sprint(path: Path, sprint: Sprint) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	lines = [
		f"id: {sprint.id}",
		f"name: {sprint.name}",
		f"start_date: {sprint.start_date.isoformat()}",
		f"end_date: {sprint.end_date.isoformat()}",
		"tickets:",
	]
	for ticket_id in sprint.tickets:
		lines.append(f"  - {ticket_id}")
	lines.extend(
		[
			f"status: {sprint.status}",
			f"velocity_points: {sprint.velocity_points}",
			f"completed_points: {sprint.completed_points}",
		]
	)
	path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_sprint(path: Path) -> Sprint:
	data: dict = {"tickets": []}
	current_list = None

	for raw_line in path.read_text(encoding="utf-8").splitlines():
		line = raw_line.strip()
		if not line:
			continue
		if line == "tickets:":
			current_list = "tickets"
			continue
		if line.startswith("-") and current_list == "tickets":
			data["tickets"].append(line.lstrip("- "))
			continue

		current_list = None
		if ":" in line:
			key, value = line.split(":", 1)
			data[key.strip()] = value.strip()

	return Sprint(
		id=data["id"],
		name=data["name"],
		start_date=date.fromisoformat(data["start_date"]),
		end_date=date.fromisoformat(data["end_date"]),
		tickets=data.get("tickets", []),
		status=data.get("status", "active"),
		velocity_points=int(data.get("velocity_points", 0)),
		completed_points=int(data.get("completed_points", 0)),
	)
