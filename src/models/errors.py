"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppError(Exception):
    code: str
    message: str
    http_status: int = 500
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class ConfigError(AppError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(
            code="config_error",
            message=message,
            http_status=500,
            retryable=False,
            details=details or {},
        )


class ValidationError(AppError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(
            code="validation_error",
            message=message,
            http_status=400,
            retryable=False,
            details=details or {},
        )


class ExternalServiceError(AppError):
    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        retryable: bool = True,
    ):
        super().__init__(
            code="external_service_error",
            message=message,
            http_status=502,
            retryable=retryable,
            details=details or {},
        )


class StorageError(AppError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(
            code="storage_error",
            message=message,
            http_status=500,
            retryable=True,
            details=details or {},
        )


class ProcessingError(AppError):
    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ):
        super().__init__(
            code="processing_error",
            message=message,
            http_status=500,
            retryable=retryable,
            details=details or {},
        )


class NotFoundError(AppError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(
            code="not_found",
            message=message,
            http_status=404,
            retryable=False,
            details=details or {},
        )


class RateLimitError(AppError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(
            code="rate_limit",
            message=message,
            http_status=429,
            retryable=True,
            details=details or {},
        )


def from_exception(exc: Exception, fallback_message: str = "Unhandled processing error") -> AppError:
    if isinstance(exc, AppError):
        return exc
    return ProcessingError(
        fallback_message,
        details={"exception": exc.__class__.__name__},
    )
