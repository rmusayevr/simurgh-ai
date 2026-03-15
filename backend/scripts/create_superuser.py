"""
Create or promote a superuser account.

Usage (via Makefile):
    make superuser

Usage (directly inside a running container):
    python scripts/create_superuser.py
    python scripts/create_superuser.py --email admin@example.com --password secret
"""

import argparse
import asyncio
import getpass
import sys

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User, UserRole


async def create_or_promote(email: str, password: str) -> None:
    engine = create_async_engine(str(settings.DATABASE_URL))
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        existing = (
            await session.exec(select(User).where(User.email == email.lower()))
        ).first()

        if existing:
            print(f"User '{email}' already exists — promoting to superuser.")
            existing.is_superuser = True
            existing.role = UserRole.ADMIN
            existing.is_active = True
            existing.email_verified = True
            session.add(existing)
        else:
            user = User(
                email=email.lower(),
                hashed_password=hash_password(password),
                full_name="Admin",
                role=UserRole.ADMIN,
                is_superuser=True,
                is_active=True,
                email_verified=True,
                terms_accepted=True,
            )
            session.add(user)

        await session.commit()

    await engine.dispose()
    print(f"✓ Superuser '{email}' ready. Login at http://localhost:5173/login")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or promote a superuser.")
    parser.add_argument("--email", default=None)
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    email = args.email or input("Admin email: ").strip()
    if not email:
        print("Email cannot be empty.", file=sys.stderr)
        sys.exit(1)

    password = args.password or getpass.getpass("Password: ")
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)

    asyncio.run(create_or_promote(email, password))


if __name__ == "__main__":
    main()
