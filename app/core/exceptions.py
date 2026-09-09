"""Application exception hierarchy.

Every raised exception carries an `ErrorCode` so callers (workers, API layer)
can react deterministically instead of string-matching messages.
"""

from __future__ import annotations

from typing import Any

from app.core.errors import ErrorCode, is_retryable


class AppError(Exception):
    """Base class for all deliberate application errors."""

    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    http_status: int = 500

    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode | None = None,
        http_status: int | None = None,
        context: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.context: dict[str, Any] = context or {}
        self.__cause__ = cause

    @property
    def retryable(self) -> bool:
        return is_retryable(self.code)

    def to_public_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "message": self.message}

    def __str__(self) -> str:  # pragma: no cover - trivial
        ctx = " ".join(f"{k}={v!r}" for k, v in self.context.items())
        return f"[{self.code.value}] {self.message}" + (f" ({ctx})" if ctx else "")


class ConfigError(AppError):
    code = ErrorCode.CONFIG_MISSING
    http_status = 500


class ValidationError(AppError):
    code = ErrorCode.VALIDATION_ERROR
    http_status = 422


class NotFoundError(AppError):
    code = ErrorCode.NOT_FOUND
    http_status = 404


class UnauthorizedError(AppError):
    code = ErrorCode.UNAUTHORIZED
    http_status = 401


class LocationError(AppError):
    code = ErrorCode.LOCATION_INVALID
    http_status = 400


class ProviderError(AppError):
    """A discovery / search provider failed. Usually non-fatal to the job."""

    code = ErrorCode.PROVIDER_UNAVAILABLE
    http_status = 502

    def __init__(self, message: str, *, provider: str, **kwargs: Any) -> None:
        context = kwargs.pop("context", {}) or {}
        context.setdefault("provider", provider)
        super().__init__(message, context=context, **kwargs)
        self.provider = provider


class WebsiteError(AppError):
    code = ErrorCode.WEBSITE_INVALID
    http_status = 502


class LLMError(AppError):
    code = ErrorCode.LLM_UNAVAILABLE
    http_status = 502


class DatabaseError(AppError):
    code = ErrorCode.DATABASE_ERROR
    http_status = 503


class RedisError(AppError):
    code = ErrorCode.REDIS_ERROR
    http_status = 503


class JobError(AppError):
    code = ErrorCode.JOB_FAILED
    http_status = 500


class OutreachError(AppError):
    code = ErrorCode.OUTREACH_NOT_CONFIGURED
    http_status = 409
