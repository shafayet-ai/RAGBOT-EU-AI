from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User, UserRole
from .config import get_settings
from .database import get_db

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
DUMMY_PASSWORD_HASH = password_context.hash("EU-AI login timing sentinel")


def _jwt_secret() -> str:
    secret = get_settings().secret_key
    if secret is None or len(secret.get_secret_value()) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT authentication is not securely configured.",
        )
    return secret.get_secret_value()


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_context.verify(plain_password, hashed_password)


def create_access_token(subject: UUID) -> str:
    settings = get_settings()
    if settings.algorithm not in {"HS256", "HS384", "HS512"}:
        raise RuntimeError("ALGORITHM must be one of HS256, HS384, or HS512.")
    if settings.access_token_expire_minutes <= 0:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive.")
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        {"sub": str(subject), "exp": expires_at},
        _jwt_secret(),
        algorithm=settings.algorithm,
    )


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    settings = get_settings()
    if settings.algorithm not in {"HS256", "HS384", "HS512"}:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT authentication is not securely configured.",
        )
    try:
        payload = jwt.decode(
            token, _jwt_secret(), algorithms=[settings.algorithm]
        )
        user_id = UUID(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError) as exc:
        raise credentials_error from exc

    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise credentials_error
    return user


def require_role(required_roles: list[str]):
    allowed_roles = {UserRole(role) for role in required_roles}

    async def role_guard(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )
        return current_user

    return role_guard
