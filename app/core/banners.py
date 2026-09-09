"""Human-readable terminal banners for job/config failures (spec section 71)."""

from __future__ import annotations

import sys

_LINE = "=" * 60


def job_failed_banner(
    *,
    job_id: str,
    job_type: str,
    stage: str | None,
    error_code: str | None,
    error_message: str | None,
    action: str | None = None,
) -> None:
    lines = [
        _LINE,
        f"{job_type} JOB FAILED",
        _LINE,
        "",
        f"Job ID:   {job_id}",
        f"Stage:    {stage or '-'}",
        f"Error:    {error_code or 'UNKNOWN'}",
        f"Detail:   {error_message or '-'}",
    ]
    if action:
        lines += ["", "Action:", *[f"- {a}" for a in action.splitlines()]]
    lines += ["", _LINE, ""]
    print("\n".join(lines), file=sys.stderr)


def provider_fallback_banner(*, job_id: str, failed: str, error: str, falling_back_to: list[str]) -> None:
    print(
        "\n".join(
            [
                _LINE,
                "DISCOVERY PROVIDER DEGRADED",
                _LINE,
                f"Job ID:   {job_id}",
                f"Provider: {failed}",
                f"Error:    {error}",
                "",
                "Action:",
                *[f"- falling back to {p}" for p in falling_back_to],
                _LINE,
                "",
            ]
        ),
        file=sys.stderr,
    )
