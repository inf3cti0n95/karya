"""Pydantic models for Karya."""

from __future__ import annotations

from datetime import date, datetime
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


class EpicType(str, Enum):
	INITIATIVE = "initiative"
	FEATURE = "feature"
	SPIKE = "spike"
	MIGRATION = "migration"
	PLATFORM = "platform"


class EpicStatus(str, Enum):
	PLANNED = "planned"
	ACTIVE = "active"
	BLOCKED = "blocked"
	DONE = "done"


class ADRStatus(str, Enum):
	PROPOSED = "proposed"
	ACCEPTED = "accepted"
	DEPRECATED = "deprecated"
	SUPERSEDED = "superseded"


import re

def normalize_tag(tag: str) -> str:
	tag = tag.lower()
	tag = re.sub(r'[\s_]+', '-', tag)
	return re.sub(r'[^a-z0-9-]', '', tag)


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
	epic: Optional[str] = None
	tags: list[str] = Field(default_factory=list)

	dependencies: list[str] = Field(default_factory=list)
	blocked_by: list[str] = Field(default_factory=list)

	estimated_effort: int = Field(default=1, ge=1, le=5)
	linked_adrs: list[str] = Field(default_factory=list)

	goal_text: Optional[str] = None
	tasks: list[dict] = Field(default_factory=list)
	acceptance_criteria: list[dict] = Field(default_factory=list)
	execution_log: list[dict] = Field(default_factory=list)
	notes_text: Optional[str] = None

	path: Optional[Path] = None


class Epic(BaseModel):
	model_config = ConfigDict(str_strip_whitespace=True, strict=True)

	id: str
	title: str
	type: EpicType = EpicType.FEATURE
	priority: Priority = Priority.MEDIUM

	created_at: datetime
	updated_at: datetime

	tags: list[str] = Field(default_factory=list)
	linked_adrs: list[str] = Field(default_factory=list)

	goal_text: Optional[str] = None
	success_metrics: list[str] = Field(default_factory=list)
	notes_text: Optional[str] = None

	path: Optional[Path] = None


class ADR(BaseModel):
	model_config = ConfigDict(str_strip_whitespace=True, strict=True)

	id: str
	title: str
	status: ADRStatus = ADRStatus.PROPOSED

	date: date

	linked_tickets: list[str] = Field(default_factory=list)
	linked_epics: list[str] = Field(default_factory=list)
	tags: list[str] = Field(default_factory=list)

	supersedes: Optional[str] = None
	superseded_by: Optional[str] = None

	context_text: Optional[str] = None
	decision_text: Optional[str] = None
	consequences_text: Optional[str] = None
	alternatives_text: Optional[str] = None

	path: Optional[Path] = None
