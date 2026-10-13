import argparse
import asyncio
import getpass
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / "root" / ".env")

from .core.database import get_session_factory
from .core.security import hash_password
from .models import User, UserRole
from .schemas import RegisterRequest


async def create_or_promote_admin(
    email: str,
    full_name: str,
    password: str,
    student_id: str,
) -> None:
    validated = RegisterRequest(
        student_id=student_id,
        email=email,
        full_name=full_name,
        password=password,
    )
    factory = get_session_factory()
    async with factory() as session:
        user = await session.scalar(
            select(User).where(User.email == validated.email)
        )
        if user is None:
            user = User(
                email=validated.email,
                student_id=validated.student_id,
                full_name=validated.full_name,
                hashed_password=hash_password(validated.password),
                role=UserRole.ADMIN,
            )
            session.add(user)
        else:
            user.role = UserRole.ADMIN
            user.student_id = validated.student_id
            user.full_name = validated.full_name
            user.hashed_password = hash_password(validated.password)
        await session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create or promote an EU-AI administrator account."
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", required=True)
    parser.add_argument("--student-id", required=True)
    args = parser.parse_args()
    password = getpass.getpass("Admin password (12-72 UTF-8 bytes): ")
    confirmation = getpass.getpass("Confirm admin password: ")
    if password != confirmation:
        parser.error("Passwords do not match.")
    asyncio.run(
        create_or_promote_admin(
            args.email, args.full_name, password, args.student_id
        )
    )
    print(f"Administrator account configured for {args.email.strip().lower()}.")


if __name__ == "__main__":
    main()
