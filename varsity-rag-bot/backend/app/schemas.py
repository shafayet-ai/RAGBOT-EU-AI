from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .models import UserRole


class RegisterRequest(BaseModel):
    student_id: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9-]*$")
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=12, max_length=72)

    model_config = ConfigDict(extra="forbid")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("student_id")
    @classmethod
    def normalize_student_id(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, value: str) -> str:
        full_name = value.strip()
        if not full_name:
            raise ValueError("Full name cannot be blank.")
        return full_name

    @field_validator("password")
    @classmethod
    def enforce_bcrypt_length(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes.")
        return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: str | None = None
    email: EmailStr
    full_name: str
    role: UserRole
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None
    language: Literal["en", "bn"] = "en"

    @field_validator("message", mode="before")
    @classmethod
    def strip_message(cls, value: str) -> str:
        return value.strip()


class Citation(BaseModel):
    title: str
    url: str | None = None
    page: int | None = None
    section: str | None = None
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Citation]
    confidence: float | None = None
    grounded: bool
    conversation_id: UUID


class AdminUsersResponse(BaseModel):
    users: list[UserResponse]
    total: int


class AdminOverview(BaseModel):
    application: str
    application_version: str
    python_version: str
    rag_provider: str
    chat_model: str
    embedding_model: str
    vector_store: str
    database_engine: str
    database_status: Literal["connected"]
    user_count: int
    chat_count: int
    source_document_count: int
    indexed_chunk_count: int


class AdminDocument(BaseModel):
    filename: str
    size_bytes: int
    modified_at: datetime
    managed: bool


class AdminDocumentsResponse(BaseModel):
    documents: list[AdminDocument]
    total: int


class ReindexResponse(BaseModel):
    indexed_chunk_count: int
    source_document_count: int
    message: str
