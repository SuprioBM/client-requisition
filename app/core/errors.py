"""Structured error taxonomy shared across the system.

Internal code uses `ErrorCode` everywhere. The API layer maps these to safe,
consistent HTTP responses (see `app/api/errors.py`).
"""

from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    # configuration
    CONFIG_MISSING = "CONFIG_MISSING"
    CONFIG_INVALID = "CONFIG_INVALID"

    # location resolution
    LOCATION_INVALID = "LOCATION_INVALID"
    LOCATION_AMBIGUOUS = "LOCATION_AMBIGUOUS"
    LOCATION_UNRESOLVED = "LOCATION_UNRESOLVED"

    # discovery / search providers
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_AUTH_FAILED = "PROVIDER_AUTH_FAILED"
    PROVIDER_BAD_RESPONSE = "PROVIDER_BAD_RESPONSE"
    PROVIDER_QUOTA_EXCEEDED = "PROVIDER_QUOTA_EXCEEDED"

    # website research
    WEBSITE_TIMEOUT = "WEBSITE_TIMEOUT"
    WEBSITE_BLOCKED = "WEBSITE_BLOCKED"
    WEBSITE_NOT_FOUND = "WEBSITE_NOT_FOUND"
    WEBSITE_INVALID = "WEBSITE_INVALID"
    WEBSITE_TOO_LARGE = "WEBSITE_TOO_LARGE"
    WEBSITE_SSRF_BLOCKED = "WEBSITE_SSRF_BLOCKED"
    PLAYWRIGHT_FAILED = "PLAYWRIGHT_FAILED"

    # infrastructure
    DATABASE_ERROR = "DATABASE_ERROR"
    REDIS_ERROR = "REDIS_ERROR"

    # LLM
    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_RATE_LIMITED = "LLM_RATE_LIMITED"
    LLM_INVALID_OUTPUT = "LLM_INVALID_OUTPUT"
    LLM_AUTH_FAILED = "LLM_AUTH_FAILED"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"

    # jobs / workflow
    JOB_FAILED = "JOB_FAILED"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    JOB_INVALID_STATE = "JOB_INVALID_STATE"

    # outreach
    OUTREACH_NOT_CONFIGURED = "OUTREACH_NOT_CONFIGURED"
    DUPLICATE_OUTREACH = "DUPLICATE_OUTREACH"
    OUTREACH_NOT_APPROVED = "OUTREACH_NOT_APPROVED"

    # generic
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# Which error codes represent transient conditions that are safe to retry.
RETRYABLE_ERROR_CODES: frozenset[ErrorCode] = frozenset(
    {
        ErrorCode.PROVIDER_TIMEOUT,
        ErrorCode.PROVIDER_RATE_LIMITED,
        ErrorCode.PROVIDER_UNAVAILABLE,
        ErrorCode.WEBSITE_TIMEOUT,
        ErrorCode.PLAYWRIGHT_FAILED,
        ErrorCode.DATABASE_ERROR,
        ErrorCode.REDIS_ERROR,
        ErrorCode.LLM_TIMEOUT,
        ErrorCode.LLM_RATE_LIMITED,
        ErrorCode.LLM_UNAVAILABLE,
    }
)

# Error codes that must never be retried (permanent / operator action required).
NON_RETRYABLE_ERROR_CODES: frozenset[ErrorCode] = frozenset(
    {
        ErrorCode.CONFIG_MISSING,
        ErrorCode.CONFIG_INVALID,
        ErrorCode.PROVIDER_AUTH_FAILED,
        ErrorCode.PROVIDER_QUOTA_EXCEEDED,
        ErrorCode.LLM_AUTH_FAILED,
        ErrorCode.LOCATION_INVALID,
        ErrorCode.WEBSITE_SSRF_BLOCKED,
        ErrorCode.VALIDATION_ERROR,
    }
)


def is_retryable(code: ErrorCode) -> bool:
    return code in RETRYABLE_ERROR_CODES
