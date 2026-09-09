"""Reusable fakes so the test-suite needs zero paid APIs (spec section 76)."""

from __future__ import annotations

from app.db.models.enums import ProviderName
from app.discovery.base import BusinessCandidate, BusinessDiscoveryProvider, ProviderRun


class MockDiscoveryProvider(BusinessDiscoveryProvider):
    def __init__(
        self,
        name: ProviderName,
        candidates: list[BusinessCandidate] | None = None,
        *,
        fail_with: str | None = None,
        is_available: bool = True,
    ) -> None:
        self.name = name
        self._candidates = candidates or []
        self._fail_with = fail_with
        self._available = is_available
        self.calls: list[str] = []

    async def available(self) -> bool:
        return self._available

    async def search(self, query: str, **kw: object) -> ProviderRun:
        self.calls.append(query)
        run = ProviderRun(provider=self.name, query=query)
        if self._fail_with:
            run.status = "failed"
            run.error_code = self._fail_with
            run.error_message = f"mock failure {self._fail_with}"
            return run
        for c in self._candidates:
            c = c.model_copy(update={"search_query": query, "provider": self.name})
            run.candidates.append(c)
        run.result_count = len(run.candidates)
        return run


def make_candidate(name: str, **kw: object) -> BusinessCandidate:
    base: dict = {
        "business_name": name,
        "provider": ProviderName.GOOGLE_PLACES,
        "city": "Dhaka",
        "country": "Bangladesh",
    }
    base.update(kw)
    return BusinessCandidate(**base)


class FakeLLMClient:
    """Drop-in for app.evaluation.llm.LLMClient. Canned responses keyed by label.

    A response may be a dict (validated against the schema) or a callable
    (prompt -> dict). Missing label -> raises, so tests are explicit.
    """

    model_name = "fake-model"

    def __init__(self, responses: dict[str, object] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[dict] = []

    async def structured(self, label: str, schema, user_prompt: str, *, system: str = ""):  # type: ignore[no-untyped-def]
        self.calls.append({"label": label, "prompt": user_prompt})
        if label not in self.responses:
            raise KeyError(f"FakeLLMClient has no canned response for {label!r}")
        val = self.responses[label]
        if callable(val):
            val = val(user_prompt)
        return schema.model_validate(val), {"label": label, "status": "ok", "model": self.model_name}


DEFAULT_LLM_RESPONSES: dict[str, object] = {
    "pain_points": {
        "pain_points": [
            {
                "category": "WEBSITE",
                "title": "No online booking flow",
                "description": "The researched pages expose no online appointment mechanism, "
                "so customers appear to book by phone.",
                "evidence_ids": [],
                "confidence": "POSSIBLE",
            }
        ]
    },
    "solutions": {
        "solutions": [
            {
                "pain_point_title": "No online booking flow",
                "service_category": "WEB DEVELOPMENT",
                "service_name": "Booking Systems",
                "why_it_fits": "Adds an online appointment request flow tied to the observed gap.",
                "expected_value": "Fewer missed calls; easier after-hours booking requests.",
                "confidence": "POSSIBLE",
                "fit_rank": 1,
            }
        ]
    },
    "opportunity": {
        "is_opportunity": True,
        "summary": "There is a plausible booking-friction opportunity backed by website evidence.",
        "reasoning": "Evidence shows no booking mechanism; confidence is moderate.",
        "commercial_potential": "MEDIUM",
        "contactable": True,
        "outreach_worthwhile": True,
    },
    "scoring": {
        "problem_severity": 14,
        "business_value": 16,
        "evidence_confidence": 11,
        "solution_fit": 15,
        "contactability": 7,
        "reasons": {"problem_severity": "single medium-confidence pain point"},
    },
    "outreach_strategy": {
        "primary_observation": "No online booking flow on the site.",
        "primary_problem": "Booking friction for customers.",
        "primary_solution": "Online appointment booking system.",
        "value_proposition": "Make appointment requests easier and reduce phone load.",
        "tone": "professional, concise",
        "call_to_action": "Offer a short call to show a demo.",
        "evidence_ids": [],
    },
    "email": {
        "subject": "A quick note about online booking",
        "body": "Hi, I came across your clinic while researching dentists in the area. "
        "I noticed appointments seem to be handled by phone rather than an online form. "
        "A simple booking page could make requests easier for your patients. "
        "Happy to show you what I mean on a short call. Thanks, Suprio",
    },
    "whatsapp": {
        "body": "Hi! Saw your clinic while researching local dentists. Noticed there's no online "
        "booking on the site. I think a small booking page could help. Happy to show you. - Suprio",
    },
}
