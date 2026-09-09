"""Manual end-to-end smoke test against the REAL configured APIs.

    python scripts/run_e2e.py --industry dentist --city Dhaka --country Bangladesh

Runs: discovery -> pick one prospect with a website -> research -> evaluate ->
generate outreach -> approve + attempt send. Prints a readable report.

Needs GOOGLE_MAPS_API_KEY (or Brave) and GROQ_API_KEY in .env. Costs a handful
of API calls. Not a substitute for `pytest` (which needs no paid services).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

from app.core.logging import configure_logging  # noqa: E402


async def main(industry: str, city: str, country: str, target: int) -> None:
    configure_logging()
    from app.db.models.evaluation import EvaluationRun, PainPoint, Solution
    from app.db.models.outreach import OutreachMessage
    from app.db.models.prospect import Prospect
    from app.db.session import session_scope
    from app.services import outreach_service
    from app.services.discovery_service import run_discovery_pipeline
    from app.services.evaluation_service import run_evaluation
    from sqlalchemy import select

    print("=" * 60, "\nSTAGE 1  DISCOVERY\n", "=" * 60, sep="")
    summary = await run_discovery_pipeline(
        industry=industry, city=city, country=country, radius_km=8, target_leads=target
    )
    print(f"  created={summary.prospects_created} updated={summary.prospects_updated} "
          f"unique={summary.unique_clusters} raw={summary.raw_candidates}")
    for r in summary.provider_runs:
        print(f"  {r['provider']:14} {r['query'][:34]:34} {r['status']:8} n={r['result_count']}")

    async with session_scope() as s:
        p = (
            await s.execute(select(Prospect).where(Prospect.website.is_not(None)).limit(1))
        ).scalars().first()
    if p is None:
        print("no prospect with a website found")
        return

    print("\n", "=" * 60, f"\nSTAGE 2-4  RESEARCH + EVALUATION + OUTREACH\n  {p.business_name}\n",
          "=" * 60, sep="")
    res = await run_evaluation(p.id, force_research=True)
    sc = res["score"]
    print(f"  opportunity={res['is_opportunity']} commercial={res['commercial_potential']} "
          f"score={sc['total']}/100")
    print("  " + "  ".join(f"{k}={v}" for k, v in sc.items() if isinstance(v, int)))

    async with session_scope() as s:
        run = (await s.execute(select(EvaluationRun).where(
            EvaluationRun.prospect_id == p.id).order_by(EvaluationRun.created_at.desc()))
        ).scalars().first()
        pps = (await s.execute(select(PainPoint).where(
            PainPoint.evaluation_run_id == run.id))).scalars().all()
        sols = (await s.execute(select(Solution).where(
            Solution.evaluation_run_id == run.id))).scalars().all()
        msgs = (await s.execute(select(OutreachMessage).where(
            OutreachMessage.prospect_id == p.id))).scalars().all()

    print("\n  PAIN POINTS")
    for pp in pps:
        print(f"   [{pp.confidence}] {pp.category}: {pp.title}  (cites {len(pp.evidence_ids)} evidence)")
    print("\n  SOLUTIONS")
    for so in sorted(sols, key=lambda x: x.fit_rank):
        print(f"   #{so.fit_rank} {so.service_category} / {so.service_name}  [{so.confidence}]")

    print("\n  OUTREACH DRAFTS")
    for m in msgs:
        print(f"\n   --- {m.channel} [{m.status}] to={m.to_address or '(none)'} ---")
        if m.subject:
            print(f"   Subject: {m.subject}")
        for line in m.body.splitlines():
            print("   " + line)

    email = next((m for m in msgs if m.channel == "EMAIL"), None)
    if email and email.status == "PENDING_APPROVAL":
        print("\n", "=" * 60, "\nSTAGE 5  HUMAN APPROVAL + SEND\n", "=" * 60, sep="")
        print("  approve:", await outreach_service.approve(email.id, actor="run_e2e"))
        print("  send   :", await outreach_service.send(email.id, actor="run_e2e"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--industry", default="dentist")
    ap.add_argument("--city", default="Dhaka")
    ap.add_argument("--country", default="Bangladesh")
    ap.add_argument("--target", type=int, default=12)
    a = ap.parse_args()
    asyncio.run(main(a.industry, a.city, a.country, a.target))
