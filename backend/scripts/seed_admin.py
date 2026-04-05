"""
Seed the default admin user for local development.

Creates admin@admin.com / admin123 if it doesn't already exist.

Usage (from backend/):
    python scripts/seed_admin.py

Requires:
    - docker compose up -d db
    - alembic upgrade head
"""

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.models.user import ROLE_ADMIN, User
from app.services.auth_service import hash_password

ADMIN_EMAIL = "admin@admin.com"
ADMIN_PASSWORD = "admin123"


async def seed() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.email == ADMIN_EMAIL))
        if result.scalar_one_or_none():
            print(f"Admin already exists: {ADMIN_EMAIL}")
            await engine.dispose()
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
        print(f"Created admin: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")

    await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(seed())
    except Exception as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
