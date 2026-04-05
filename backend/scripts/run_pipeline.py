"""
Full pipeline walkthrough script.

Demonstrates the complete RBAC flow then runs the QuickHire assessment pipeline:

  1. Seed an admin user directly in the DB (no bootstrap endpoint needed)
  2. Admin logs in -> JWT
  3. Admin invites an org manager (creating the QuickHire org)
  4. Manager registers via invite token
  5. Manager invites an underwriter
  6. Underwriter registers via invite token
  7. Upload documents and run the assessment pipeline (X-API-Key, existing endpoints)
  8. Manager grants underwriter access to the completed assessment
  9. Verify underwriter can see the assessment
 10. Download PDF report
 11. Post-run cleanup

Usage (from backend/):
    python scripts/run_pipeline.py

Requires:
    - docker compose up -d db minio minio-init
    - API running: uvicorn app.main:app --reload
    - ANTHROPIC_API_KEY set in .env
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
API_KEY = "change-me-in-production-use-a-long-random-string"
SLUG = "quickhire-demo"
DOCS_DIR = Path(__file__).parent.parent.parent / "test_data" / "company_b_quickhire"
REPORT_OUT = Path(__file__).parent.parent / "report_output.pdf"

# Demo credentials (only used in dev/demo)
ADMIN_EMAIL = "admin@camille.dev"
ADMIN_PASSWORD = "AdminDemo1!"
MANAGER_EMAIL = "manager@quickhire.dev"
MANAGER_PASSWORD = "ManagerDemo1!"
UNDERWRITER_EMAIL = "underwriter@quickhire.dev"
UNDERWRITER_PASSWORD = "UnderwriterDemo1!"

# X-API-Key header for existing pipeline endpoints
API_HEADERS = {"X-API-Key": API_KEY}


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


def _get_db_engine():  # type: ignore[return]
    """Bootstrap a direct SQLAlchemy engine for seeding / cleanup ops."""
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).parent.parent))
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://camille:localdev@localhost:5433/camille",
    )
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import settings

    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


# ── Cleanup ───────────────────────────────────────────────────────────────────


def cleanup(label: str) -> None:
    """Delete all demo data: access grants, invitations, users, assessments, org."""
    print(f"\n[{label}] Cleaning up demo data (slug='{SLUG}') ...")
    try:
        import asyncio

        from sqlalchemy import delete, select

        from app.models.assessment import Assessment
        from app.models.document import Document
        from app.models.invitation import Invitation
        from app.models.organization import Organization
        from app.models.user import User
        from app.models.user_assessment_access import UserAssessmentAccess

        engine, SessionLocal = _get_db_engine()

        async def _delete() -> None:
            async with SessionLocal() as db:
                # Org (may not exist yet on pre-run)
                org_result = await db.execute(select(Organization).where(Organization.slug == SLUG))
                org = org_result.scalar_one_or_none()

                if org:
                    # Assessments + their access grants and documents
                    assessments = await db.execute(select(Assessment).where(Assessment.organization_id == org.id))
                    for a in assessments.scalars().all():
                        await db.execute(delete(UserAssessmentAccess).where(UserAssessmentAccess.assessment_id == a.id))
                        await db.execute(delete(Document).where(Document.assessment_id == a.id))
                    await db.execute(delete(Assessment).where(Assessment.organization_id == org.id))

                    # Invitations for this org
                    await db.execute(delete(Invitation).where(Invitation.organization_id == org.id))
                    # Users in this org
                    await db.execute(delete(User).where(User.organization_id == org.id))
                    # Org itself
                    await db.execute(delete(Organization).where(Organization.id == org.id))
                    print(f"  deleted org {org.id} + its users/assessments/invitations")
                else:
                    print("  no org found")

                # Admin user (no org)
                await db.execute(delete(User).where(User.email == ADMIN_EMAIL))
                # Admin-role invitations (no org)
                await db.execute(
                    delete(Invitation).where(Invitation.email.in_([MANAGER_EMAIL, UNDERWRITER_EMAIL, ADMIN_EMAIL]))
                )
                await db.commit()
            await engine.dispose()

        asyncio.run(_delete())
    except Exception as exc:
        print(f"  cleanup error (non-fatal): {exc}")


# ── Admin seed ────────────────────────────────────────────────────────────────


def seed_admin() -> None:
    """
    Create the first admin user directly in the DB.
    There is no public bootstrap endpoint - platform admins are seeded this way
    or promoted via DB tooling in production.
    """
    print("\n[SEED] Creating admin user directly in DB ...")
    try:
        import asyncio

        from sqlalchemy import select

        from app.models.user import ROLE_ADMIN, User
        from app.services.auth_service import hash_password

        engine, SessionLocal = _get_db_engine()

        async def _seed() -> None:
            async with SessionLocal() as db:
                existing = await db.execute(select(User).where(User.email == ADMIN_EMAIL))
                if existing.scalar_one_or_none():
                    print(f"  admin already exists: {ADMIN_EMAIL}")
                    return
                admin = User(
                    email=ADMIN_EMAIL,
                    hashed_password=hash_password(ADMIN_PASSWORD),
                    role=ROLE_ADMIN,
                    organization_id=None,
                    is_active=True,
                )
                db.add(admin)
                await db.commit()
                print(f"  created admin: {ADMIN_EMAIL}")
            await engine.dispose()

        asyncio.run(_seed())
    except Exception as exc:
        print(f"  seed failed: {exc}")
        sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    # Pre-run cleanup so re-runs are always fresh
    cleanup("PRE-RUN")

    # Seed the admin user into the DB before any HTTP calls
    seed_admin()

    with httpx.Client(timeout=60) as client:
        # ── SECTION 1: RBAC FLOW ─────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("  SECTION 1 — RBAC / AUTH FLOW")
        print("=" * 60)

        # 1a. Admin login
        admin_auth = check(
            client.post(
                f"{BASE}/auth/login",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            ),
            "Admin login",
        )
        admin_token = admin_auth["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        pp("Admin user", admin_auth["user"])

        # 1b. Admin invites org manager - creates org in one step
        manager_invite = check(
            client.post(
                f"{BASE}/invitations/manager",
                json={
                    "email": MANAGER_EMAIL,
                    "org_name": "QuickHire (Demo)",
                    "org_slug": SLUG,
                },
                headers=admin_headers,
            ),
            "Admin invites org manager (creates org)",
        )
        pp("Manager invitation", manager_invite)
        manager_invite_token = manager_invite["token"]
        org_id = manager_invite["organization_id"]

        # 1c. Manager registers with the invite token
        manager_auth = check(
            client.post(
                f"{BASE}/auth/register",
                params={"invite_token": manager_invite_token},
                json={"password": MANAGER_PASSWORD},
            ),
            "Manager registers from invite",
        )
        manager_token = manager_auth["access_token"]
        manager_headers = {"Authorization": f"Bearer {manager_token}"}
        pp("Manager user", manager_auth["user"])

        # 1d. Manager invites underwriter into their org
        uw_invite = check(
            client.post(
                f"{BASE}/invitations/underwriter",
                json={"email": UNDERWRITER_EMAIL},
                headers=manager_headers,
            ),
            "Manager invites underwriter",
        )
        pp("Underwriter invitation", uw_invite)
        uw_invite_token = uw_invite["token"]

        # 1e. Underwriter registers
        uw_auth = check(
            client.post(
                f"{BASE}/auth/register",
                params={"invite_token": uw_invite_token},
                json={"password": UNDERWRITER_PASSWORD},
            ),
            "Underwriter registers from invite",
        )
        uw_token = uw_auth["access_token"]
        uw_headers = {"Authorization": f"Bearer {uw_token}"}
        pp("Underwriter user", uw_auth["user"])

        # 1f. Admin lists all users in the platform
        all_users = check(
            client.get(f"{BASE}/users", headers=admin_headers),
            "Admin lists all users",
        )
        pp(f"All users ({all_users['total']} total)", all_users["users"])

        # 1g. Manager lists users in their org
        org_users = check(
            client.get(f"{BASE}/users/org/{org_id}", headers=manager_headers),
            "Manager lists org users",
        )
        pp(f"Org users ({org_users['total']} in org)", org_users["users"])

        uw_user_id = uw_auth["user"]["id"]

        # ── SECTION 2: PIPELINE ──────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("  SECTION 2 — ASSESSMENT PIPELINE")
        print("=" * 60)

        # 2a. Create assessment (existing endpoint, X-API-Key)
        assessment = check(
            client.post(
                f"{BASE}/assessments",
                json={"organization_id": org_id},
                headers=API_HEADERS,
            ),
            "Create assessment",
        )
        pp("Assessment", assessment)
        a_id = assessment["id"]

        # 2b. Upload documents
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
                    headers=API_HEADERS,
                )
            check(resp, f"  Upload {doc_path.name}")

        # 2c. Trigger pipeline
        trigger = check(
            client.post(f"{BASE}/assessments/{a_id}/process", headers=API_HEADERS),
            "Trigger pipeline",
        )
        pp("Pipeline triggered", trigger)

        # 2d. Poll until complete
        print("\n[POLL] Waiting for pipeline to complete ...")
        elapsed = 0
        while True:
            time.sleep(5)
            elapsed += 5
            status_resp = client.get(f"{BASE}/assessments/{a_id}", headers=API_HEADERS)
            data = status_resp.json()
            status = data.get("status", "unknown")
            print(f"  {time.strftime('%H:%M:%S')}  [{elapsed:>3}s]  status: {status}")
            if status == "complete":
                break
            if status == "failed":
                print("\n✗  Pipeline failed")
                pp("Assessment detail", data)
                sys.exit(1)

        # 2e. Print scores
        scores = check(
            client.get(f"{BASE}/assessments/{a_id}/scores", headers=API_HEADERS),
            "Get scores",
        )
        pp("SCORES", scores)

        overall = scores["overall_score"]
        tier = scores["risk_tier"]
        passed = 48 <= overall <= 58 and tier == "medium"

        print(f"\n{'─' * 60}")
        print(f"  RESULT: overall_score={overall:.1f}  risk_tier={tier}")
        if passed:
            print("  PASS - score in expected range [48, 58], tier=medium")
        else:
            print(f"  FAIL - expected [48, 58] / medium, got {overall:.1f} / {tier}")
        print(f"{'─' * 60}")

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
                print(f"    x  [{dim_label}] {f.get('text', '')}")

        # ── SECTION 3: ACCESS CONTROL ────────────────────────────────────────
        print("\n" + "=" * 60)
        print("  SECTION 3 — UNDERWRITER ACCESS CONTROL")
        print("=" * 60)

        # 3a. Manager grants underwriter access to the assessment
        grant = check(
            client.post(
                f"{BASE}/users/org/{org_id}/assessments/{a_id}/grant",
                json={"user_id": uw_user_id},
                headers=manager_headers,
            ),
            "Manager grants underwriter access to assessment",
        )
        pp("Access grant", grant)

        # 3b. Confirm underwriter identity
        uw_me = check(
            client.get(f"{BASE}/auth/me", headers=uw_headers),
            "Underwriter /me",
        )
        pp("Underwriter identity", uw_me)

        print(f"\n  Underwriter '{uw_me['email']}' (role: {uw_me['role']}) now has access")
        print(f"  to assessment {a_id} in org {org_id}.")
        print("  (Frontend would call GET /assessments/{id} with Bearer token)")

        # ── SECTION 4: EXTERNAL SIGNALS ──────────────────────────────────────
        print("\n" + "=" * 60)
        print("  SECTION 4 — EXTERNAL SIGNALS")
        print("=" * 60)

        signals_resp = client.get(
            f"{BASE}/signals/search",
            params={"company": "QuickHire"},
            headers=API_HEADERS,
            timeout=60,
        )
        if signals_resp.status_code == 200:
            signals_data = signals_resp.json()
            if signals_data:
                pp(f"External Signals ({len(signals_data)} found)", signals_data)
                severity_counts: dict[str, int] = {}
                for s in signals_data:
                    sev = s.get("severity", "unknown")
                    severity_counts[sev] = severity_counts.get(sev, 0) + 1
                print(f"\n  Severity breakdown: {severity_counts}")
            else:
                print("  (no signals found - NEWS_API_KEY may not be configured)")
        else:
            print(f"  signals/search returned [{signals_resp.status_code}]: {signals_resp.text[:200]}")

        # ── SECTION 5: PDF REPORT ─────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("  SECTION 5 — PDF REPORT")
        print("=" * 60)

        report_resp = client.get(
            f"{BASE}/assessments/{a_id}/report",
            headers=API_HEADERS,
            follow_redirects=True,
        )

        if report_resp.status_code == 200 and report_resp.headers.get("content-type", "").startswith("application/pdf"):
            REPORT_OUT.write_bytes(report_resp.content)
            size_kb = len(report_resp.content) / 1024
            print(f"  Saved -> {REPORT_OUT}  ({size_kb:.0f} KB)")
            print("\n  Opening report ...")
            open_file(REPORT_OUT)
        elif report_resp.status_code == 404:
            print("  Report not generated yet (report_generator may not be wired in).")
        else:
            print(f"  Unexpected response [{report_resp.status_code}]: {report_resp.text[:200]}")

        # ── Post-run cleanup ─────────────────────────────────────────────────
        cleanup("POST-RUN")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
