"""Schema and business rule validation."""

from __future__ import annotations

import re

from karya.core.models import Ticket

_TICKET_ID_RE = re.compile(r"^TICKET-\d+$")


def validate_ticket(ticket: Ticket) -> list[str]:
	errors: list[str] = []

	if not _TICKET_ID_RE.match(ticket.id):
		errors.append("Ticket id must match pattern TICKET-<digits>.")

	title = ticket.title.strip() if ticket.title else ""
	if not title:
		errors.append("Ticket title must be non-empty.")
	elif len(title) > 200:
		errors.append("Ticket title must be under 200 characters.")

	if not 1 <= ticket.estimated_effort <= 5:
		errors.append("Estimated effort must be between 1 and 5.")

	if ticket.id in ticket.dependencies:
		errors.append("Ticket cannot depend on itself.")

	if any(not agent.strip() for agent in ticket.agents_allowed):
		errors.append("agents_allowed cannot contain empty strings.")

	return errors


def validate_completable(ticket: Ticket) -> list[str]:
	unchecked: list[str] = []
	for item in ticket.acceptance_criteria:
		if not item.get("done"):
			unchecked.append(item.get("text", ""))
	return unchecked
