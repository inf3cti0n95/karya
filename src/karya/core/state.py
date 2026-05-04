"""State machine for ticket transitions."""

from __future__ import annotations

from typing import Dict, List

from karya.exceptions import InvalidTransitionError

VALID_TRANSITIONS: Dict[str, List[str]] = {
    "backlog": ["todo"],
    "todo": ["in-progress", "backlog"],
    "in-progress": ["done", "blocked"],
    "blocked": ["in-progress", "todo"],
    "done": [],
}


def validate_transition(current: str, new: str) -> None:
    options = VALID_TRANSITIONS.get(current, [])
    if new not in options:
        message = (
            f"Invalid transition from '{current}' to '{new}'. "
            f"Valid options: {options}."
        )
        raise InvalidTransitionError(message)


def get_valid_transitions(current: str) -> List[str]:
    return list(VALID_TRANSITIONS.get(current, []))
