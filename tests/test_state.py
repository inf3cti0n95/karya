"""State machine tests."""

import pytest

from karya.core.state import VALID_TRANSITIONS, get_valid_transitions, validate_transition
from karya.exceptions import InvalidTransitionError


def test_get_valid_transitions_backlog() -> None:
    assert "todo" in get_valid_transitions("backlog")


def test_validate_transition_invalid() -> None:
    with pytest.raises(InvalidTransitionError):
        validate_transition("done", "backlog")


def test_valid_transitions() -> None:
    for current, options in VALID_TRANSITIONS.items():
        for option in options:
            validate_transition(current, option)


def test_done_is_terminal() -> None:
    assert get_valid_transitions("done") == []


def test_invalid_transition_message() -> None:
    with pytest.raises(InvalidTransitionError) as exc:
        validate_transition("todo", "done")
    message = str(exc.value)
    assert "todo" in message and "done" in message
