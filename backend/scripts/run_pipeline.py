"""
Full pipeline walkthrough script.

Creates an org + assessment, uploads all QuickHire documents, triggers the
pipeline, polls until complete, then prints scores. Cleans up (deletes the
assessment + org records) at start and end so re-runs are always fresh.

Usage (from backend/):
    python scripts/run_pipeline.py

Requires:
    - API running: uvicorn app.main:app --reload
    - API_KEY_SECRET set in .env (default: change-me-in-production-use-a-long-random-string)
"""

import json
import sys
import time
from pathlib import Path

import httpx

# ── Config ────────────────────────────────────────────────────────────────────
BASE = "http://localhost:8000/api/v1"
KEY  = "change-me-in-production-use-a-long-random-string"
SLUG = "quickhire-demo"
DOCS_DIR = Path(__file__).parent.parent.parent / "test_data" / "company_b_quickhire"

HEADERS = {"X-API-Key": KEY}


def pp(label: str, data: dict | list) -> None:
    print(f"\n{'─'*60}")
    print(f"  {label}")
    print(f"{'─'*60}")
    print(json.dumps(data, indent=2, default=str))


def check(resp: httpx.Response, label: str) -> dict:
    if resp.status_code >= 400:
        print(f"\n✗  {label} failed [{resp.status_code}]")
        print(resp.text)
        sys.exit(1)
    data = resp.json()
    print(f"✓  {label} [{resp.status_code}]")
    return data


# ── Cleanup helper ─────────────────────────────────────────────────────────────
def cleanup(client: httpx.Client, label: str) -> None:
    """Delete the demo org and all its assessments via direct DB — API has no
    DELETE endpoints yet, so we use SQLAlchemy directly."""
    print(f"\n[{label}] Cleaning up slug='{SLUG}' ...")
    try:
        # Import here so the script still works if run outside the venv with DB
        import os
        sys.path.insert(0, str(Path(__file__).parent.parent))
        os.environ.setdefault("DATABASE_URL",
            "postgresql+asyncpg://camille:localdev@localhost:5433/camille")

        import asyncio
        from sqlalchemy import delete, select
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from app.config import settings
        from app.models.assessment import Assessment
        from app.models.document import Document
        from app.models.organization import Organization

        engine = create_async_engine(settings.DATABASE_URL)
        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

        async def _delete() -> None:
            async with SessionLocal() as db:
                result = await db.execute(
                    select(Organization).where(Organization.slug == SLUG)
                )
                org = result.scalar_one_or_none()
                if not org:
                    print("  nothing to clean up")
                    return
                # Delete documents → assessments → org
                assessments = await db.execute(
                    select(Assessment).where(Assessment.organization_id == org.id)
                )
                for a in assessments.scalars().all():
                    await db.execute(delete(Document).where(Document.assessment_id == a.id))
                await db.execute(
                    delete(Assessment).where(Assessment.organization_id == org.id)
                )
                await db.execute(delete(Organization).where(Organization.id == org.id))
                await db.commit()
                print(f"  deleted org {org.id}")
            await engine.dispose()

        asyncio.run(_delete())
    except Exception as exc:
        print(f"  cleanup skipped: {exc}")


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    with httpx.Client(headers=HEADERS, timeout=30) as client:

        # ── Pre-run cleanup ──────────────────────────────────────────────────
        cleanup(client, "PRE-RUN")

        # ── 1. Create org ────────────────────────────────────────────────────
        org = check(
            client.post(f"{BASE}/organizations",
                        json={"name": "QuickHire (Demo)", "slug": SLUG}),
            "Create org",
        )
        pp("Organization", org)
        org_id = org["id"]

        # ── 2. Create assessment ─────────────────────────────────────────────
        assessment = check(
            client.post(f"{BASE}/assessments", json={"organization_id": org_id}),
            "Create assessment",
        )
        pp("Assessment", assessment)
        a_id = assessment["id"]

        # ── 3. Upload documents ──────────────────────────────────────────────
        docs = sorted(DOCS_DIR.glob("*.txt"))
        if not docs:
            print(f"\n✗  No .txt files found in {DOCS_DIR}")
            sys.exit(1)

        print(f"\n[UPLOAD] Uploading {len(docs)} documents ...")
        for doc_path in docs:
            with open(doc_path, "rb") as f:
                resp = client.post(
                    f"{BASE}/assessments/{a_id}/documents",
                    files={"file": (doc_path.name, f, "text/plain")},
                )
            check(resp, f"  Upload {doc_path.name}")

        # ── 4. Trigger pipeline ──────────────────────────────────────────────
        trigger = check(
            client.post(f"{BASE}/assessments/{a_id}/process"),
            "Trigger pipeline",
        )
        pp("Pipeline triggered", trigger)

        # ── 5. Poll until complete ───────────────────────────────────────────
        print("\n[POLL] Waiting for pipeline to complete ...")
        while True:
            time.sleep(4)
            status_resp = client.get(f"{BASE}/assessments/{a_id}")
            data = status_resp.json()
            status = data.get("status", "unknown")
            print(f"  {time.strftime('%H:%M:%S')}  status: {status}")
            if status == "complete":
                break
            if status == "failed":
                print("\n✗  Pipeline failed")
                pp("Assessment detail", data)
                sys.exit(1)

        # ── 6. Get scores ────────────────────────────────────────────────────
        scores = check(
            client.get(f"{BASE}/assessments/{a_id}/scores"),
            "Get scores",
        )
        pp("SCORES", scores)

        overall = scores["overall_score"]
        tier    = scores["risk_tier"]
        passed  = 48 <= overall <= 58 and tier == "medium"

        print(f"\n{'─'*60}")
        print(f"  RESULT: overall_score={overall:.1f}  risk_tier={tier}")
        print(f"  {'✓ PASS — within expected range [48, 58]' if passed else '✗ FAIL — outside expected range [48, 58]'}")
        print(f"{'─'*60}")

        # ── Post-run cleanup ─────────────────────────────────────────────────
        cleanup(client, "POST-RUN")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
