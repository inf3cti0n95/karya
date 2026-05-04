"""Pydantic models for Karya."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TicketStatus(str, Enum):
	BACKLOG = "backlog"
	TODO = "todo"
	IN_PROGRESS = "in-progress"
	BLOCKED = "blocked"
	DONE = "done"


class TicketType(str, Enum):
	FEATURE = "feature"
	BUG = "bug"
	CHORE = "chore"
	SPIKE = "spike"
	INFRA = "infra"


class Priority(str, Enum):
	CRITICAL = "critical"
	HIGH = "high"
	MEDIUM = "medium"
	LOW = "low"


class Ticket(BaseModel):
	model_config = ConfigDict(str_strip_whitespace=True, strict=True)

	id: str
	title: str
	status: TicketStatus
	type: TicketType = TicketType.FEATURE
	priority: Priority = Priority.MEDIUM

	created_at: datetime
	updated_at: datetime

	owner: Optional[str] = None
	agents_allowed: list[str] = Field(default_factory=list)

	epic: Optional[str] = None
	sprint: Optional[str] = None

	dependencies: list[str] = Field(default_factory=list)
	blocked_by: list[str] = Field(default_factory=list)

	estimated_effort: int = Field(default=1, ge=1, le=5)
	labels: list[str] = Field(default_factory=list)

	context_text: Optional[str] = None
	goal_text: Optional[str] = None
	scope_text: Optional[str] = None
	tasks: list[dict] = Field(default_factory=list)
	acceptance_criteria: list[dict] = Field(default_factory=list)
	execution_log: list[dict] = Field(default_factory=list)
	agent_instructions: Optional[str] = None

	path: Optional[Path] = None

	@property
	def is_completable(self) -> bool:
		return all(item.get("done") for item in self.acceptance_criteria)


class Event(BaseModel):
	model_config = ConfigDict(strict=True)

	event: str
	ticket_id: Optional[str] = None
	timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
	actor: Optional[str] = None
	data: dict = Field(default_factory=dict)


class Sprint(BaseModel):
	model_config = ConfigDict(strict=True)

	id: str
	name: str
	start_date: date
	end_date: date
	tickets: list[str] = Field(default_factory=list)
	status: str = "active"
	velocity_points: int = 0
	completed_points: int = 0
