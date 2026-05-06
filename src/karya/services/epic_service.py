"""Epic service operations."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import frontmatter

from karya.core.filesystem import (
    EPICS_DIR,
    append_event,
    find_epic_path,
    generate_epic_id,
    init_karya,
    normalize_root,
    write_epic_file,
)
from karya.core.models import Epic, EpicStatus, EpicType, Event, Priority, TicketStatus
from karya.core.parser import parse_epic, serialize_epic
from karya.exceptions import EpicArchivedError, EpicNotFoundError, UpdateForbiddenError
from karya.git.integration import GitIntegration
from karya.services.index_service import IndexService
from karya.services.ticket_service import TicketService

_UPDATE_FIELDS = {
    "title",
    "priority",
    "tags",
    "owner",
    "goal_text",
    "context_text",
    "success_metrics",
    "parent_epic",
    "linked_adrs",
    "child_epics",
}


class EpicService:
    def __init__(self, root: Path):
        self.root = normalize_root(root)
        self._tickets = TicketService(root)
        self._git = GitIntegration(root)
        self._index = IndexService(root)

    def create(
        self,
        title: str,
        type: EpicType = EpicType.FEATURE,
        priority: Priority = Priority.MEDIUM,
        goal: str = "",
        parent_epic: str | None = None,
        tags: list[str] | None = None,
        owner: str | None = None,
        actor: str | None = None,
    ) -> Epic:
        init_karya(self.root)

        epic_id = generate_epic_id(self.root)
        now = datetime.now(timezone.utc)
        epic = Epic(
            id=epic_id,
            title=title,
            type=type,
            priority=priority,
            created_at=now,
            updated_at=now,
            owner=owner,
            parent_epic=parent_epic,
            tags=tags or [],
            goal_text=goal,
        )

        path = self.root / EPICS_DIR / f"{epic_id}.md"
        epic.path = path
        self._write_epic(epic)

        append_event(Event(event="epic_created", data={"epic_id": epic_id}, actor=actor), self.root)
        self._git.commit(f"{epic_id} created ({actor or 'system'})")
        return epic

    def get(self, epic_id: str) -> Epic:
        path = find_epic_path(epic_id, self.root)
        if not path:
            raise EpicNotFoundError(f"Epic '{epic_id}' not found.")

        epic = parse_epic(path)
        epic.status, epic.progress = self._compute_status(epic)
        return epic

    def list(
        self,
        status: EpicStatus | None = None,
        tag: str | None = None,
        parent: str | None = None,
    ) -> list[Epic]:
        epics: list[Epic] = []
        for path in (self.root / EPICS_DIR).glob("EPIC-*.md"):
            epic = self.get(path.stem)
            epics.append(epic)

        if status:
            epics = [epic for epic in epics if epic.status == status]
        if tag:
            epics = [epic for epic in epics if tag in epic.tags]
        if parent:
            epics = [epic for epic in epics if epic.parent_epic == parent]

        return epics

    def update(self, epic_id: str, updates: dict, actor: str | None = None) -> Epic:
        epic = self.get(epic_id)
        if epic.status == EpicStatus.ARCHIVED:
            raise EpicArchivedError(f"Epic '{epic_id}' is archived.")

        forbidden = [field for field in updates if field not in _UPDATE_FIELDS]
        if forbidden:
            raise UpdateForbiddenError(
                f"Updates not allowed for fields: {', '.join(forbidden)}"
            )

        for field, value in updates.items():
            setattr(epic, field, value)

        self._write_epic(epic)
        append_event(
            Event(event="epic_updated", data={"epic_id": epic_id, "updates": updates}, actor=actor),
            self.root,
        )
        self._git.commit(f"{epic_id} updated ({actor or 'system'})")
        return self.get(epic_id)

    def link_ticket(self, epic_id: str, ticket_id: str, actor: str | None = None) -> Epic:
        epic = self.get(epic_id)
        if ticket_id not in epic.tickets:
            epic.tickets.append(ticket_id)

        ticket = self._tickets.get(ticket_id)
        ticket.epic = epic_id
        self._tickets._write_ticket(ticket)

        self._write_epic(epic)
        append_event(
            Event(event="epic_ticket_linked", data={"epic_id": epic_id, "ticket_id": ticket_id}, actor=actor),
            self.root,
        )
        self._git.commit(f"{epic_id} linked ticket {ticket_id} ({actor or 'system'})")
        return self.get(epic_id)

    def unlink_ticket(self, epic_id: str, ticket_id: str, actor: str | None = None) -> Epic:
        epic = self.get(epic_id)
        epic.tickets = [entry for entry in epic.tickets if entry != ticket_id]

        ticket = self._tickets.get(ticket_id)
        ticket.epic = None
        self._tickets._write_ticket(ticket)

        self._write_epic(epic)
        append_event(
            Event(event="epic_ticket_unlinked", data={"epic_id": epic_id, "ticket_id": ticket_id}, actor=actor),
            self.root,
        )
        self._git.commit(f"{epic_id} unlinked ticket {ticket_id} ({actor or 'system'})")
        return self.get(epic_id)

    def link_adr(self, epic_id: str, adr_id: str, actor: str | None = None) -> Epic:
        epic = self.get(epic_id)
        if adr_id not in epic.linked_adrs:
            epic.linked_adrs.append(adr_id)
        self._write_epic(epic)

        append_event(
            Event(event="epic_adr_linked", data={"epic_id": epic_id, "adr_id": adr_id}, actor=actor),
            self.root,
        )
        self._git.commit(f"{epic_id} linked adr {adr_id} ({actor or 'system'})")
        return self.get(epic_id)

    def describe(self, epic_id: str) -> dict:
        epic = self.get(epic_id)
        data = epic.model_dump(mode="json")
        if epic.path:
            data["path"] = str(epic.path)

        ticket_states = []
        for ticket_id in epic.tickets:
            try:
                ticket = self._tickets.get(ticket_id)
                ticket_states.append({"id": ticket_id, "status": ticket.status.value})
            except Exception:
                ticket_states.append({"id": ticket_id, "status": "missing"})

        data["tickets_detail"] = ticket_states
        return data

    def archive(self, epic_id: str, reason: str, actor: str | None = None) -> Epic:
        epic = self.get(epic_id)
        epic.status = EpicStatus.ARCHIVED
        self._write_epic(epic)
        append_event(
            Event(event="epic_archived", data={"epic_id": epic_id, "reason": reason}, actor=actor),
            self.root,
        )
        self._git.commit(f"{epic_id} archived ({actor or 'system'})")
        return self.get(epic_id)

    def _compute_status(self, epic: Epic) -> tuple[EpicStatus, dict]:
        if epic.status == EpicStatus.ARCHIVED:
            return EpicStatus.ARCHIVED, {"done": 0, "total": 0, "pct": 0}

        if not epic.tickets:
            return EpicStatus.PLANNED, {"done": 0, "total": 0, "pct": 0}

        statuses = []
        for ticket_id in epic.tickets:
            ticket = self._tickets.get(ticket_id)
            statuses.append(ticket.status)

        total = len(statuses)
        done = sum(1 for status in statuses if status == TicketStatus.DONE)
        in_progress = any(status == TicketStatus.IN_PROGRESS for status in statuses)
        blocked = any(status == TicketStatus.BLOCKED for status in statuses)

        if done == total:
            status = EpicStatus.DONE
        elif in_progress:
            status = EpicStatus.ACTIVE
        elif blocked:
            status = EpicStatus.BLOCKED
        else:
            status = EpicStatus.PLANNED

        pct = int((done / total) * 100) if total else 0
        return status, {"done": done, "total": total, "pct": pct}

    def _write_epic(self, epic: Epic) -> None:
        serialized = serialize_epic(epic)
        post = frontmatter.loads(serialized)
        if not epic.path:
            raise EpicNotFoundError("Epic path missing.")
        write_epic_file(epic.path, post.metadata, post.content)
        self._index.update_entity("epic", epic.id)
