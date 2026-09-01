"""Shared repository protocol contracts."""

from typing import Protocol

class SessionScopedRepository(Protocol):
    """A repository bound to one unit-of-work session."""
