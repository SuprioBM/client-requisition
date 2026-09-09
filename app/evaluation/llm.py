"""Groq LLM client for structured evaluation/outreach output.

- LangChain (`ChatGroq`) provides model/tool integration.
- We request JSON, parse it, and validate against a Pydantic schema.
- Invalid output -> one constrained retry ("return ONLY valid JSON matching ...").
- Every call records latency / token usage / status for observability.
- Failures map to ErrorCode (LLM_TIMEOUT / LLM_RATE_LIMITED / LLM_AUTH_FAILED /
  LLM_INVALID_OUTPUT / LLM_UNAVAILABLE).

A test / offline `LLMClient` can be injected via `set_llm_client`.
"""

from __future__ import annotations

import json
import re
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.core.errors import ErrorCode
from app.core.exceptions import LLMError
from app.core.logging import get_logger

log = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

EVALUATOR_SYSTEM = """You are evaluating a potential B2B service opportunity for a
software/automation consultant.

You are NOT a salesperson looking for a reason to sell. Your job is to determine
whether there is a legitimate, evidence-backed opportunity.

RULES (strict):
- Use ONLY the supplied evidence. Every evidence item has an id.
- Cite the evidence id(s) that support each meaningful claim.
- If the evidence is insufficient for a claim, say so / use NOT_ENOUGH_EVIDENCE.
- Never fabricate business processes, internal tooling, staffing, budgets or revenue.
- Never claim a technology exists or does not exist unless evidence supports it.
- Never assume willingness or ability to pay.
- Prefer conservative conclusions. "Unknown" is not "a problem".
- Return ONLY valid minified JSON. No prose, no markdown, no code fences.
"""

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


class _RealGroq:
    def __init__(self) -> None:
        s = get_settings()
        if not s.groq_api_key:
            raise LLMError("GROQ_API_KEY not configured", code=ErrorCode.LLM_AUTH_FAILED)
        from langchain_groq import ChatGroq

        self._model_name = s.groq_model
        self._chat = ChatGroq(
            model=s.groq_model,
            api_key=s.groq_api_key,
            temperature=0.2,
            max_retries=0,
            timeout=45,
            model_kwargs={"response_format": {"type": "json_object"}},
        )

    @property
    def model_name(self) -> str:
        return self._model_name

    async def complete_json(self, system: str, user: str) -> tuple[str, dict]:
        from langchain_core.messages import HumanMessage, SystemMessage

        resp = await self._chat.ainvoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        meta = getattr(resp, "response_metadata", {}) or {}
        usage = getattr(resp, "usage_metadata", {}) or meta.get("token_usage", {}) or {}
        return str(resp.content), {
            "model": self._model_name,
            "input_tokens": usage.get("input_tokens") or usage.get("prompt_tokens"),
            "output_tokens": usage.get("output_tokens") or usage.get("completion_tokens"),
            "finish_reason": meta.get("finish_reason"),
        }


class LLMClient:
    """Schema-validating wrapper around a raw JSON completion backend."""

    def __init__(self, backend: object | None = None) -> None:
        self._backend = backend

    def _get_backend(self) -> object:
        if self._backend is None:
            self._backend = _RealGroq()
        return self._backend

    @property
    def model_name(self) -> str:
        return getattr(self._get_backend(), "model_name", "unknown")

    async def structured(
        self, label: str, schema: type[T], user_prompt: str, *, system: str = EVALUATOR_SYSTEM
    ) -> tuple[T, dict]:
        backend = self._get_backend()
        attempts = 0
        last_err: str | None = None
        prompt = user_prompt
        rate_limit_retries = 0
        t0 = time.perf_counter()
        while attempts < 2:
            attempts += 1
            try:
                raw, meta = await backend.complete_json(system, prompt)  # type: ignore[attr-defined]
            except Exception as exc:  # noqa: BLE001
                code = _classify_llm_error(exc)
                if code == ErrorCode.LLM_RATE_LIMITED and rate_limit_retries < 8:
                    rate_limit_retries += 1
                    delay = _retry_after_seconds(str(exc))
                    log.warning("llm.rate_limited", label=label, retry_in=delay,
                                attempt=rate_limit_retries)
                    import asyncio

                    await asyncio.sleep(delay)
                    attempts -= 1
                    continue
                log.error("llm.call.failed", label=label, error=str(exc), error_code=code.value)
                raise LLMError(f"{label}: {exc}", code=code) from exc

            parsed, err = _parse(raw, schema)
            if parsed is not None:
                latency = int((time.perf_counter() - t0) * 1000)
                obs = {
                    **meta,
                    "label": label,
                    "attempts": attempts,
                    "latency_ms": latency,
                    "status": "ok",
                }
                log.info("llm.call.ok", label=label, attempts=attempts, latency_ms=latency,
                         model=meta.get("model"))
                return parsed, obs
            last_err = err
            required = list(schema.model_json_schema().get("properties", {}).keys())
            prompt = (
                f"{user_prompt}\n\nYour previous reply was invalid ({err}). "
                f"Return ONLY one minified JSON object with keys {required}. "
                "No markdown, no code fences, no commentary."
            )

        raise LLMError(
            f"{label}: model did not return valid JSON after {attempts} attempts ({last_err})",
            code=ErrorCode.LLM_INVALID_OUTPUT,
        )


def _parse(raw: str, schema: type[T]) -> tuple[T | None, str | None]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{") :] if "{" in text else text
    m = _JSON_RE.search(text)
    if not m:
        return None, "no JSON object found in response"
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        return None, f"JSON decode error: {exc}"
    try:
        return schema.model_validate(data), None
    except ValidationError as exc:
        return None, f"schema validation: {exc.errors()[:3]}"


def _retry_after_seconds(message: str) -> float:
    m = re.search(r"try again in ([0-9.]+)s", message)
    if m:
        return min(60.0, float(m.group(1)) + 0.5)
    return 15.0


def _classify_llm_error(exc: Exception) -> ErrorCode:
    msg = str(exc).lower()
    if "timeout" in msg or "timed out" in msg:
        return ErrorCode.LLM_TIMEOUT
    if "rate" in msg or "429" in msg:
        return ErrorCode.LLM_RATE_LIMITED
    if "auth" in msg or "401" in msg or "api key" in msg or "invalid_api_key" in msg:
        return ErrorCode.LLM_AUTH_FAILED
    if "context" in msg and ("length" in msg or "window" in msg or "too large" in msg):
        return ErrorCode.LLM_INVALID_OUTPUT
    return ErrorCode.LLM_UNAVAILABLE


_client: LLMClient | None = None


def set_llm_client(client: LLMClient | None) -> None:
    global _client
    _client = client


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
