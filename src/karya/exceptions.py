"""Custom exceptions for Karya."""


class KaryaError(Exception):
    """Base error for Karya."""


class TicketNotFoundError(KaryaError):
    """Raised when a ticket cannot be located."""


class InvalidTransitionError(KaryaError):
    """Raised when a state transition is invalid."""


class ValidationError(KaryaError):
    """Raised when validation fails."""


class UpdateForbiddenError(KaryaError):
    """Raised when attempting to update a forbidden field."""


class IncompleteAcceptanceCriteria(KaryaError):
    """Raised when acceptance criteria are incomplete for completion."""

    def __init__(self, unchecked: list[str]):
        super().__init__("Acceptance criteria incomplete.")
        self.unchecked = unchecked


class SprintNotFoundError(KaryaError):
    """Raised when an active sprint cannot be found."""


class DuplicateTicketError(KaryaError):
    """Raised when a duplicate ticket is detected."""
