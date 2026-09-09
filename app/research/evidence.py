"""Turn deterministic signals into Evidence records.

Each item: an objective observation, its source, and a calibrated confidence.
These are the ONLY facts the LLM evaluator is allowed to reason from.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.db.models.enums import DataOrigin, EvidenceType
from app.research.signals import ResearchSignals


def _ev(
    evidence_type: EvidenceType,
    source_type: str,
    observation: str,
    confidence: float,
    *,
    source_url: str | None = None,
    extracted_text: str | None = None,
    origin: DataOrigin = DataOrigin.VERIFIED,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "evidence_type": evidence_type.value,
        "source_type": source_type,
        "source_url": source_url,
        "observation": observation,
        "confidence": round(confidence, 2),
        "data_origin": origin.value,
        "extracted_text": extracted_text,
        "extra": extra or {},
        "collected_at": datetime.now(UTC).isoformat(),
    }


def build_evidence(
    *,
    prospect: dict,
    signals: ResearchSignals,
    extracted_text: str | None,
    tavily_results: list[dict] | None = None,
) -> list[dict[str, Any]]:
    ev: list[dict[str, Any]] = []
    ws = signals.website
    url = ws.final_url or prospect.get("website")

    # ---- website status ----
    if not prospect.get("website"):
        ev.append(_ev(EvidenceType.WEBSITE_STATUS, "direct_http",
                      "No website was found for this business in discovery data.", 0.7))
    elif ws.status == "ACTIVE":
        ev.append(_ev(EvidenceType.WEBSITE_STATUS, "direct_http",
                      f"The website responded successfully (status {ws.status}).", 0.9,
                      source_url=url))
    elif ws.status in ("TIMEOUT", "SERVER_ERROR", "FORBIDDEN", "NOT_FOUND", "INVALID"):
        ev.append(_ev(EvidenceType.WEBSITE_STATUS, "direct_http",
                      f"The website could not be researched directly (status {ws.status}).", 0.75,
                      source_url=url))

    if ws.pages_analyzed:
        # ---- structure ----
        if ws.is_https is False:
            ev.append(_ev(EvidenceType.WEBSITE_STRUCTURE, "direct_http",
                          "The website was served over plain HTTP (no HTTPS) on the researched page.",
                          0.85, source_url=url))
        if ws.has_meta_description is False:
            ev.append(_ev(EvidenceType.WEBSITE_STRUCTURE, "direct_http",
                          "The researched page has no meta description.", 0.7, source_url=url))
        if ws.has_viewport_meta is False:
            ev.append(_ev(EvidenceType.WEBSITE_STRUCTURE, "direct_http",
                          "The researched page has no responsive viewport meta tag, a "
                          "possible indicator of a non-mobile-optimised layout.", 0.55,
                          source_url=url))
        if ws.has_primary_cta is False:
            ev.append(_ev(EvidenceType.WEBSITE_STRUCTURE, "direct_http",
                          "No clear primary call-to-action text was identified on the "
                          "researched pages.", 0.5, source_url=url))
        else:
            ev.append(_ev(EvidenceType.WEBSITE_STRUCTURE, "direct_http",
                          f"Call-to-action text present: {', '.join(ws.cta_texts[:5])}.", 0.7,
                          source_url=url))

        # ---- booking / ordering ----
        if ws.has_booking_mechanism is False:
            ev.append(_ev(EvidenceType.WEBSITE_CONTENT, "direct_http",
                          "No online appointment/booking mechanism was identified on the "
                          "researched pages.", 0.6, source_url=url))
        if ws.has_online_ordering is False and (signals.business.category or "").lower() in (
            "restaurant", "cafe", "food", "bakery", "retail"
        ):
            ev.append(_ev(EvidenceType.WEBSITE_CONTENT, "direct_http",
                          "No online ordering flow was identified on the researched pages.", 0.55,
                          source_url=url))

        # ---- contact channels ----
        if ws.has_contact_form is False and ws.has_contact_email is False:
            ev.append(_ev(EvidenceType.CONTACT_CHANNEL, "direct_http",
                          "No contact form or email address was found on the researched pages; "
                          "contact appears to rely on phone or in-person interaction.", 0.5,
                          source_url=url))
        if ws.has_live_chat:
            ev.append(_ev(EvidenceType.TECHNOLOGY_SIGNAL, "direct_http",
                          "A live-chat widget was detected on the website.", 0.75, source_url=url))

        # ---- content / info architecture ----
        if ws.total_text_length < 400:
            ev.append(_ev(EvidenceType.WEBSITE_CONTENT, "direct_http",
                          "The researched pages contain very little textual content "
                          f"(~{ws.total_text_length} characters).", 0.6, source_url=url))
        if not ws.service_pages_found:
            ev.append(_ev(EvidenceType.WEBSITE_CONTENT, "direct_http",
                          "No dedicated services/treatments section was identified in the "
                          "navigation or headings of the researched pages.", 0.45, source_url=url))
        if ws.has_faq_section is False:
            ev.append(_ev(EvidenceType.WEBSITE_CONTENT, "direct_http",
                          "No FAQ section was identified on the researched pages.", 0.4,
                          source_url=url))

        if ws.technology_signals:
            ev.append(_ev(EvidenceType.TECHNOLOGY_SIGNAL, "direct_http",
                          f"Technology fingerprints observed: {', '.join(ws.technology_signals[:6])}.",
                          0.6, source_url=url, origin=DataOrigin.INFERRED))

    # ---- social presence ----
    if ws.social_profiles:
        for platform, link in ws.social_profiles.items():
            ev.append(_ev(EvidenceType.SOCIAL_PRESENCE, "direct_http",
                          f"A public {platform} profile is linked from the website.", 0.8,
                          source_url=link))
    elif ws.pages_analyzed:
        ev.append(_ev(EvidenceType.SOCIAL_PRESENCE, "direct_http",
                      "No social media profiles were linked from the researched pages.", 0.45,
                      source_url=url))

    # ---- business signals (from discovery providers) ----
    b = signals.business
    if b.rating is not None and b.review_count is not None:
        ev.append(_ev(EvidenceType.BUSINESS_SIGNAL, "google_places",
                      f"The business has a {b.rating} rating across {b.review_count} reviews.",
                      0.9, extra={"rating": b.rating, "review_count": b.review_count}))
    if b.review_count is not None and b.review_count < 10:
        ev.append(_ev(EvidenceType.BUSINESS_SIGNAL, "google_places",
                      f"The business has few public reviews ({b.review_count}).", 0.6))
    if b.contact_channels:
        ev.append(_ev(EvidenceType.CONTACT_CHANNEL, "google_places",
                      f"Publicly listed contact channels: {', '.join(b.contact_channels)}.", 0.85))

    # ---- tavily fallback evidence ----
    for r in (tavily_results or [])[:4]:
        snippet = (r.get("content") or "")[:400]
        if snippet:
            ev.append(_ev(EvidenceType.SEARCH_RESULT, "tavily",
                          f"Public web source: {snippet}", 0.4,
                          source_url=r.get("url"), extracted_text=snippet,
                          origin=DataOrigin.INFERRED))

    # attach a compact extracted-text sample to the first content evidence for traceability
    if extracted_text:
        ev.append(_ev(EvidenceType.WEBSITE_CONTENT, "trafilatura",
                      "Representative extracted homepage text (sample).", 0.5,
                      source_url=url, extracted_text=extracted_text[:1500]))

    return ev
