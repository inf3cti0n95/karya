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


class EpicNotFoundError(KaryaError):
    """Raised when an epic cannot be located."""


class EpicArchivedError(KaryaError):
    """Raised when attempting to modify an archived epic."""


class ADRNotFoundError(KaryaError):
    """Raised when an ADR cannot be located."""


class ADRFrozenError(KaryaError):
    """Raised when attempting to modify content fields of an accepted ADR."""

    def __init__(self, adr_id: str, field: str):
        self.adr_id = adr_id
        self.field = field
        super().__init__(
            f"ADR {adr_id} is accepted and frozen. Field '{field}' cannot be modified. Supersede it instead."
        )


class IndexError(KaryaError):
    """Raised when an error occurs during indexing or search."""


class InvalidLinkError(KaryaError):
    """Raised when linking incompatible entity types."""


class TagValidationError(KaryaError):
    """Raised when a tag fails normalization or validation."""
