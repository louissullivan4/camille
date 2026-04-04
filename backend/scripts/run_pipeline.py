"""
Full pipeline walkthrough script.

Creates an org + assessment, uploads all QuickHire documents, triggers the
pipeline, polls until complete, prints scores, and downloads the PDF report.

Usage (from backend/):
    python scripts/run_pipeline.py

Requires:
    - docker compose up -d db minio minio-init
    - API running: uvicorn app.main:app --reload
    - ANTHROPIC_API_KEY set in .env

The script cleans up (deletes the assessment + org) at the start so re-runs
are always fresh.
"""

import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import httpx

# ── Config ────────────────────────────────────────────────────────────────────
BASE = "http://localhost:8000/api/v1"
KEY = "change-me-in-production-use-a-long-random-string"
SLUG = "quickhire-demo"
DOCS_DIR = Path(__file__).parent.parent.parent / "test_data" / "company_b_quickhire"
REPORT_OUT = Path(__file__).parent.parent / "report_output.pdf"

HEADERS = {"X-API-Key": KEY}


# ── Helpers ───────────────────────────────────────────────────────────────────


def pp(label: str, data: dict | list) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"{'─' * 60}")
    print(json.dumps(data, indent=2, default=str))


def check(resp: httpx.Response, label: str) -> dict:
    if resp.status_code >= 400:
        print(f"\n✗  {label} failed [{resp.status_code}]")
        print(resp.text)
        sys.exit(1)
    data = resp.json()
    print(f"✓  {label} [{resp.status_code}]")
    return data


def open_file(path: Path) -> None:
    """Open a file with the OS default viewer."""
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["open", str(path)], check=False)
        elif system == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception as exc:
        print(f"  (could not auto-open: {exc})")


# ── Cleanup ───────────────────────────────────────────────────────────────────


def cleanup(label: str) -> None:
    """Delete the demo org + all its assessments directly via SQLAlchemy."""
    print(f"\n[{label}] Cleaning up slug='{SLUG}' ...")
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        os.environ.setdefault(
            "DATABASE_URL",
            "postgresql+asyncpg://camille:localdev@localhost:5433/camille",
        )

        import asyncio

        from sqlalchemy import delete, select
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from app.config import settings
        from app.models.assessment import Assessment
        from app.models.document import Document
        from app.models.organization import Organization

        engine = create_async_engine(settings.DATABASE_URL)
        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

        async def _delete() -> None:
            async with SessionLocal() as db:
                result = await db.execute(select(Organization).where(Organization.slug == SLUG))
                org = result.scalar_one_or_none()
                if not org:
                    print("  nothing to clean up")
                    return
                assessments = await db.execute(select(Assessment).where(Assessment.organization_id == org.id))
                for a in assessments.scalars().all():
                    await db.execute(delete(Document).where(Document.assessment_id == a.id))
                await db.execute(delete(Assessment).where(Assessment.organization_id == org.id))
                await db.execute(delete(Organization).where(Organization.id == org.id))
                await db.commit()
                print(f"  deleted org {org.id}")
            await engine.dispose()

        asyncio.run(_delete())
    except Exception as exc:
        print(f"  cleanup skipped: {exc}")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    # Pre-run cleanup so re-runs are always fresh
    cleanup("PRE-RUN")

    with httpx.Client(headers=HEADERS, timeout=60) as client:
        # ── 1. Create org ────────────────────────────────────────────────────
        org = check(
            client.post(
                f"{BASE}/organizations",
                json={"name": "QuickHire (Demo)", "slug": SLUG},
            ),
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

        print(f"\n[UPLOAD] Uploading {len(docs)} documents from {DOCS_DIR.name} ...")
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
        elapsed = 0
        while True:
            time.sleep(5)
            elapsed += 5
            status_resp = client.get(f"{BASE}/assessments/{a_id}")
            data = status_resp.json()
            status = data.get("status", "unknown")
            print(f"  {time.strftime('%H:%M:%S')}  [{elapsed:>3}s]  status: {status}")
            if status == "complete":
                break
            if status == "failed":
                print("\n✗  Pipeline failed")
                pp("Assessment detail", data)
                sys.exit(1)

        # ── 6. Print scores ──────────────────────────────────────────────────
        scores = check(
            client.get(f"{BASE}/assessments/{a_id}/scores"),
            "Get scores",
        )
        pp("SCORES", scores)

        overall = scores["overall_score"]
        tier = scores["risk_tier"]
        passed = 48 <= overall <= 58 and tier == "medium"

        print(f"\n{'─' * 60}")
        print(f"  RESULT: overall_score={overall:.1f}  risk_tier={tier}")
        if passed:
            print("  ✓ PASS — score in expected range [48, 58], tier=medium")
        else:
            print(f"  ✗ FAIL — expected [48, 58] / medium, got {overall:.1f} / {tier}")
        print(f"{'─' * 60}")

        # Print critical flags
        dim_scores = scores.get("dimension_scores", {})
        all_flags = []
        for dim, ds in dim_scores.items():
            for flag in ds.get("flags", []):
                all_flags.append({**flag, "dimension": dim})
        critical = [f for f in all_flags if f.get("severity") == "critical"]
        if critical:
            print(f"\n  Critical flags ({len(critical)}):")
            for f in critical:
                dim_label = f.get("dimension", "").replace("_", " ").title()
                print(f"    ✗  [{dim_label}] {f.get('text', '')}")

        # ── 7. External signals search ───────────────────────────────────────
        print("\n[SIGNALS] Searching external signals for 'QuickHire' ...")
        signals_resp = client.get(
            f"{BASE}/signals/search",
            params={"company": "QuickHire"},
            timeout=60,
        )
        if signals_resp.status_code == 200:
            signals = signals_resp.json()
            if signals:
                pp(f"External Signals ({len(signals)} found)", signals)
                severity_counts: dict[str, int] = {}
                for s in signals:
                    sev = s.get("severity", "unknown")
                    severity_counts[sev] = severity_counts.get(sev, 0) + 1
                print(f"\n  Severity breakdown: {severity_counts}")
            else:
                print("  (no signals found - NEWS_API_KEY may not be configured)")
        else:
            print(f"  ⚠  signals/search returned [{signals_resp.status_code}]: {signals_resp.text[:200]}")

        # ── 8. Download PDF report ───────────────────────────────────────────
        print("\n[REPORT] Downloading PDF report ...")
        report_resp = client.get(
            f"{BASE}/assessments/{a_id}/report",
            follow_redirects=True,
        )

        if report_resp.status_code == 200 and report_resp.headers.get("content-type", "").startswith("application/pdf"):
            REPORT_OUT.write_bytes(report_resp.content)
            size_kb = len(report_resp.content) / 1024
            print(f"  ✓ Saved → {REPORT_OUT}  ({size_kb:.0f} KB)")
            print("\n  Opening report ...")
            open_file(REPORT_OUT)
        elif report_resp.status_code == 404:
            print("  ⚠  Report not generated yet (report_generator may not be wired in).")
        else:
            print(f"  ⚠  Unexpected response [{report_resp.status_code}]: {report_resp.text[:200]}")

        # ── Post-run cleanup ─────────────────────────────────────────────────
        cleanup("POST-RUN")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
