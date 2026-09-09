"""Versioned prompt builders. Each stage has its own focused prompt.

Bump PROMPT_VERSION when wording changes so historical runs stay comparable.
"""

from __future__ import annotations

import json
from typing import Any

from app.evaluation.services_kb import render_kb

PROMPT_VERSION = "v1"
SCORING_VERSION = "v1"


_MAX_EVIDENCE = 22


def _evidence_block(evidence: list[dict[str, Any]]) -> str:
    ordered = sorted(evidence, key=lambda e: float(e.get("confidence", 0)), reverse=True)
    rows = [
        {
            "id": e["id"],
            "obs": e.get("observation"),
            "src": e.get("source_type"),
            "conf": e.get("confidence"),
        }
        for e in ordered[:_MAX_EVIDENCE]
    ]
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


_WS_KEYS = (
    "status", "is_https", "has_meta_description", "has_viewport_meta", "has_primary_cta",
    "has_booking_mechanism", "has_online_ordering", "has_contact_form", "has_live_chat",
    "has_faq_section", "service_pages_found", "total_text_length", "pages_analyzed",
    "social_profiles", "technology_signals",
)


def _business_block(prospect: dict, signals: dict) -> str:
    ws = signals.get("website", {}) or {}
    return json.dumps(
        {
            "business_name": prospect.get("business_name"),
            "industry": prospect.get("industry"),
            "city": prospect.get("city"),
            "country": prospect.get("country"),
            "has_website": bool(prospect.get("website")),
            "rating": prospect.get("rating"),
            "review_count": prospect.get("review_count"),
            "website_signals": {k: ws.get(k) for k in _WS_KEYS if k in ws},
            "business_signals": signals.get("business", {}),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def pain_points_prompt(prospect: dict, signals: dict, evidence: list[dict]) -> str:
    return f"""Identify evidence-backed business/technical pain points for this business.

BUSINESS + SIGNALS:
{_business_block(prospect, signals)}

EVIDENCE (only source of truth; cite ids):
{_evidence_block(evidence)}

Categories allowed: WEBSITE, AUTOMATION, AI, BUSINESS_PROCESS, ONLINE_PRESENCE, CUSTOM_SOFTWARE.

For each candidate pain point provide: category, title, description (what the
issue plausibly is and why it matters, hedged appropriately), evidence_ids (the
ids that support it), confidence (CONFIRMED | LIKELY | POSSIBLE | NOT_ENOUGH_EVIDENCE).

Do not invent problems. If the evidence only supports 1 pain point, return 1. If
it supports none, return an empty list.

Return JSON: {{"pain_points": [ {{...}} ]}}"""


def solution_mapping_prompt(prospect: dict, pain_points: list[dict]) -> str:
    return f"""Map each pain point to the single best-fitting service from the catalogue.

PAIN POINTS:
{json.dumps(pain_points, ensure_ascii=False)}

SERVICE CATALOGUE (available services; you may also name an adjacent service if
clearly better, but prefer the catalogue):
{render_kb()}

For each pain point that has a credible solution, return: pain_point_title,
service_category, service_name, why_it_fits (tie to the pain point), expected_value
(realistic business benefit, no exaggerated metrics), confidence, fit_rank.

fit_rank must be a DISTINCT integer per solution (1 = strongest overall fit,
2 = next, ...). Do not give everything rank 1.

Skip pain points where no service is a credible fit.

Return JSON: {{"solutions": [ {{...}} ]}}"""


def opportunity_prompt(prospect: dict, signals: dict, pain_points: list[dict],
                       solutions: list[dict], evidence: list[dict]) -> str:
    return f"""Assess whether this is a legitimate outreach opportunity.

BUSINESS + SIGNALS:
{_business_block(prospect, signals)}

PAIN POINTS:
{json.dumps(pain_points, ensure_ascii=False)}

PROPOSED SOLUTIONS:
{json.dumps(solutions, ensure_ascii=False)}

EVIDENCE:
{_evidence_block(evidence)}

Decide:
- is_opportunity: is there a real, evidence-backed opportunity?
- summary: 2-3 sentences.
- reasoning: cite evidence ids; be explicit about what is uncertain.
- commercial_potential: LOW | MEDIUM | HIGH | UNKNOWN (with the reasoning covering why).
- contactable: is there a usable public contact channel?
- outreach_worthwhile: would personalised outreach be justified now?

Return JSON matching: {{"is_opportunity": bool, "summary": str, "reasoning": str,
"commercial_potential": str, "contactable": bool, "outreach_worthwhile": bool}}"""


def scoring_prompt(opportunity: dict, pain_points: list[dict], solutions: list[dict],
                   signals: dict) -> str:
    return f"""Propose sub-scores for this opportunity. Be conservative; low
evidence => low evidence_confidence.

OPPORTUNITY: {json.dumps(opportunity, ensure_ascii=False)}
PAIN POINTS: {json.dumps(pain_points, ensure_ascii=False)}
SOLUTIONS: {json.dumps(solutions, ensure_ascii=False)}
CONTACT/BUSINESS SIGNALS: {json.dumps(signals.get("business", {}), ensure_ascii=False)}

Ranges (integers):
- problem_severity 0-25  (how real / impactful the strongest pain point is)
- business_value 0-25    (value of solving it for this business)
- evidence_confidence 0-20 (how well evidence supports the conclusions)
- solution_fit 0-20      (how well an available service fits)
- contactability 0-10    (ease of reaching a decision-maker)

Also give a one-line reason per dimension in "reasons".

Return JSON matching: {{"problem_severity": int, "business_value": int,
"evidence_confidence": int, "solution_fit": int, "contactability": int,
"reasons": {{"problem_severity": str, ...}}}}"""


def outreach_strategy_prompt(prospect: dict, opportunity: dict, pain_points: list[dict],
                             solutions: list[dict], evidence: list[dict]) -> str:
    return f"""Design an outreach strategy grounded in the research.

BUSINESS: {json.dumps({k: prospect.get(k) for k in ("business_name","industry","city","country")})}
OPPORTUNITY: {json.dumps(opportunity, ensure_ascii=False)}
TOP PAIN POINTS: {json.dumps(pain_points[:3], ensure_ascii=False)}
TOP SOLUTIONS: {json.dumps(solutions[:3], ensure_ascii=False)}
EVIDENCE: {_evidence_block(evidence)}

Focus on the single strongest legitimate opportunity (not everything).

Return JSON: {{"primary_observation": str, "primary_problem": str,
"primary_solution": str, "value_proposition": str, "tone": str,
"call_to_action": str, "evidence_ids": [str]}}"""


def email_prompt(prospect: dict, strategy: dict, sender_name: str) -> str:
    return f"""Write a short, specific outreach email from {sender_name}.

BUSINESS: {prospect.get("business_name")} ({prospect.get("industry")}, {prospect.get("city")})
STRATEGY: {json.dumps(strategy, ensure_ascii=False)}

Structure: personal opening -> the specific evidence-backed observation -> the
problem/opportunity -> proposed solution -> realistic value -> soft CTA.

Hard rules: no generic agency language, no "10x", no fake statistics, no fake
compliments, no pretending to be a customer, no fabricated urgency. <=160 words.
Do NOT put evidence ids, bracketed references, or citations in the body - write
it as a normal human email. Use the business name, not "[Name]" placeholders;
if you don't know the recipient's name, address the business.

Return JSON: {{"subject": str, "body": str}}"""


def whatsapp_prompt(prospect: dict, strategy: dict, sender_name: str) -> str:
    return f"""Write a very short WhatsApp message from {sender_name} (not a copy
of the email; ~4-6 short lines).

BUSINESS: {prospect.get("business_name")} ({prospect.get("industry")}, {prospect.get("city")})
STRATEGY: {json.dumps(strategy, ensure_ascii=False)}

Mention where you came across them, the one observation, the one idea, and a soft
offer to show more. Friendly, professional, no hype. Do NOT include evidence ids,
bracketed references or citations - write it as a normal WhatsApp message. Use
the business name, not "[Name]" placeholders.

Return JSON: {{"body": str}}"""
