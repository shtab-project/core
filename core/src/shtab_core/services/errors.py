"""Compatibility imports for plugins that use the original module path."""

from shtab_core.exceptions import (
    ConflictError,
    InvalidInputError,
    NotFoundError,
    ServiceError,
    UnauthorizedError,
)

__all__ = (
    "ConflictError",
    "InvalidInputError",
    "NotFoundError",
    "ServiceError",
    "UnauthorizedError",
)
