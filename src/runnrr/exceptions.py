"""Custom exceptions for Runnrr."""


class RunnrrError(Exception):
    """Base error for Runnrr."""


class RunnrrNotInitializedError(RunnrrError):
    """Raised when .runnrr/ cannot be found by walking up the directory tree."""


class TicketNotFoundError(RunnrrError):
    """Raised when a ticket cannot be located."""


class InvalidTransitionError(RunnrrError):
    """Raised when a state transition is invalid."""


class ValidationError(RunnrrError):
    """Raised when validation fails."""


class UpdateForbiddenError(RunnrrError):
    """Raised when attempting to update a forbidden field."""


class IncompleteAcceptanceCriteria(RunnrrError):
    """Raised when acceptance criteria are incomplete for completion."""

    def __init__(self, unchecked: list[str]):
        super().__init__("Acceptance criteria incomplete.")
        self.unchecked = unchecked


class SprintNotFoundError(RunnrrError):
    """Raised when an active sprint cannot be found."""


class DuplicateTicketError(RunnrrError):
    """Raised when a duplicate ticket is detected."""


class EpicNotFoundError(RunnrrError):
    """Raised when an epic cannot be located."""


class EpicArchivedError(RunnrrError):
    """Raised when attempting to modify an archived epic."""


class ADRNotFoundError(RunnrrError):
    """Raised when an ADR cannot be located."""


class ADRFrozenError(RunnrrError):
    """Raised when attempting to modify content fields of an accepted ADR."""

    def __init__(self, adr_id: str, field: str):
        self.adr_id = adr_id
        self.field = field
        super().__init__(
            f"ADR {adr_id} is accepted and frozen. Field '{field}' cannot be modified. Supersede it instead."
        )


class IndexError(RunnrrError):
    """Raised when an error occurs during indexing or search."""


class InvalidLinkError(RunnrrError):
    """Raised when linking incompatible entity types."""


class TagValidationError(RunnrrError):
    """Raised when a tag fails normalization or validation."""
