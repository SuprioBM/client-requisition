"""Configurable knowledge base of services the consultant offers.

Default taxonomy ships in code; override by pointing SERVICES_KB_PATH at a JSON
file with the same shape. The LLM is told this is the *available* catalogue, not
an exhaustive limit.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

_DEFAULT: dict[str, list[str]] = {
    "WEB DEVELOPMENT": [
        "Business Websites",
        "E-commerce",
        "Booking Systems",
        "Web Applications",
    ],
    "AUTOMATION": [
        "Workflow Automation",
        "CRM Automation",
        "Lead Automation",
        "Notifications",
    ],
    "AI SYSTEMS": [
        "AI Chatbots",
        "RAG Systems",
        "AI Agents",
        "Document AI",
        "AI Automation",
    ],
    "CUSTOM SOFTWARE": [
        "Internal Tools",
        "Dashboards",
        "Business Management Systems",
    ],
}


@lru_cache
def get_services_kb() -> dict[str, list[str]]:
    path = os.environ.get("SERVICES_KB_PATH")
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return {str(k): [str(x) for x in v] for k, v in data.items()}
        except (OSError, ValueError, TypeError):
            pass
    return _DEFAULT


def render_kb() -> str:
    lines: list[str] = []
    for category, services in get_services_kb().items():
        lines.append(f"{category}:")
        lines.extend(f"  - {s}" for s in services)
    return "\n".join(lines)
