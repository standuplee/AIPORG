"""Structured errors shared by collector implementations."""

from collections.abc import Mapping, Sequence


class CollectorError(Exception):
    """A single provider or document operation failed."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        retryable: bool = False,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = dict(details or {})


class CollectionError(CollectorError):
    """A collection operation completed with one or more collector errors."""

    def __init__(
        self,
        *,
        message: str,
        errors: Sequence[CollectorError],
        partial: bool = False,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(
            code="collection_error",
            message=message,
            retryable=any(error.retryable for error in errors),
            details=details,
        )
        self.errors = tuple(errors)
        self.partial = partial
