from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from ....core.database import get_db
from ....core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from ....models import User, UserRole
from ....schemas import RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["authentication"])


def _is_duplicate_account_field(exc: IntegrityError) -> bool:
    constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    return constraint_name in {"uq_users_email", "uq_users_student_id"} or (
        "UNIQUE constraint failed: users.email" in str(exc.orig)
    ) or (
        "UNIQUE constraint failed: users.student_id" in str(exc.orig)
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    user = User(
        student_id=request.student_id,
        email=request.email,
        full_name=request.full_name,
        hashed_password=await run_in_threadpool(hash_password, request.password),
        role=UserRole.STUDENT,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if _is_duplicate_account_field(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email or student ID already exists.",
            ) from exc
        raise
    await session.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[AsyncSession, Depends(get_db)],
    login_type: Annotated[Literal["student", "admin"], Form()] = "student",
) -> TokenResponse:
    identifier = credentials.username.strip()
    if login_type == "student":
        user = await session.scalar(
            select(User).where(
                User.student_id == identifier.upper(),
                User.role == UserRole.STUDENT,
            )
        )
    else:
        user = await session.scalar(
            select(User).where(
                User.email == identifier.lower(),
                User.role == UserRole.ADMIN,
            )
        )
    if len(credentials.password.encode("utf-8")) > 72:
        password_matches = False
    else:
        password_matches = await run_in_threadpool(
            verify_password,
            credentials.password,
            user.hashed_password if user is not None else DUMMY_PASSWORD_HASH,
        )
    if user is None or not password_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect credentials for this account type.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user
