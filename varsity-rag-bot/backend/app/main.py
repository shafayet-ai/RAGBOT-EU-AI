import asyncio
import logging
import os
import re
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4

import yaml
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from groq import APIConnectionError, APIStatusError, RateLimitError
from langchain_core.documents import Document
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAG_ROOT = PROJECT_ROOT / "root"
sys.path.insert(0, str(RAG_ROOT))

load_dotenv(PROJECT_ROOT / "backend" / ".env")
load_dotenv(RAG_ROOT / ".env")

from rag_core import load_rag_chain  # noqa: E402

from .api.v1.router import router as api_router  # noqa: E402
from .core.database import dispose_database, get_db  # noqa: E402
from .core.security import get_current_user  # noqa: E402
from .models import ChatLog, User  # noqa: E402
from .schemas import ChatRequest, ChatResponse, Citation  # noqa: E402

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("eu_ai_api")

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_database()


app = FastAPI(
    title="EU-AI — Eastern University Knowledge Intelligence Assistant",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "FRONTEND_ORIGINS", "http://localhost:3000"
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(api_router)

NOT_FOUND_PATTERNS = (
    re.compile(r"নথিতে নেই|নথিতে পাওয়া যায়নি|প্রদত্ত নথিতে নেই"),
    re.compile(r"couldn.t find enough information|not (?:available|found) in (?:the )?(?:provided )?documents?", re.I),
)


def _citation_from_document(document: Document) -> Citation:
    source_value = document.metadata.get("source", "")
    source_path = Path(source_value) if source_value else None
    metadata: dict = {}
    if source_path and source_path.is_file() and source_path.suffix.lower() == ".md":
        try:
            source_text = source_path.read_text(encoding="utf-8")
            if source_text.startswith("---"):
                frontmatter = source_text.split("---", 2)[1]
                loaded_metadata = yaml.safe_load(frontmatter)
                if isinstance(loaded_metadata, dict):
                    metadata = loaded_metadata
        except (OSError, yaml.YAMLError):
            logger.warning("Could not read citation metadata from %s", source_path)

    page = document.metadata.get("page")
    return Citation(
        title=str(metadata.get("Document Title") or (source_path.stem if source_path else "University document")),
        url=metadata.get("Source URL"),
        page=page + 1 if isinstance(page, int) else None,
        section=metadata.get("Section"),
        snippet=" ".join(document.page_content.split())[:360],
    )


def _run_rag(message: str, language: str) -> dict:
    answer_language = "বাংলা" if language == "bn" else "English"
    return load_rag_chain(answer_language).invoke({"input": message})


@app.get("/api/v1/health")
async def health(
    session: AsyncSession = Depends(get_db),
) -> dict[str, int | str]:
    try:
        await session.execute(select(User.id).limit(0))
        await session.execute(select(ChatLog.id).limit(0))
    except SQLAlchemyError as exc:
        logger.exception("Authentication database health check failed")
        raise HTTPException(
            status_code=503,
            detail="The authentication database is unavailable.",
        ) from exc

    supported_extensions = {".pdf", ".md", ".txt"}
    directories = (
        PROJECT_ROOT / "root" / "university_docs",
        PROJECT_ROOT / "venv" / "university_docs",
        PROJECT_ROOT / "data" / "raw" / "scraped",
        PROJECT_ROOT / "data" / "raw" / "uploaded",
    )
    document_paths = {
        path.resolve()
        for directory in directories
        if directory.is_dir()
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in supported_extensions
    }
    document_count = len(document_paths)
    return {"status": "ok", "document_count": document_count}


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ChatResponse:
    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="The RAG service is not configured with a Groq API key.",
        )

    conversation_id: UUID = request.conversation_id or uuid4()
    try:
        response = await asyncio.to_thread(
            _run_rag, request.message.strip(), request.language
        )
    except RateLimitError as exc:
        logger.warning("Groq API rate limit reached")
        detail = (
            "Groq API rate limit reached. Wait before trying again or review "
            "your Groq account limits."
        )
        if request.language == "bn":
            detail = (
                "Groq API-এর অনুরোধের সীমা পূর্ণ হয়েছে। কিছুক্ষণ পরে আবার চেষ্টা "
                "করুন অথবা Groq অ্যাকাউন্টের ব্যবহারের সীমা দেখুন।"
            )
        raise HTTPException(status_code=429, detail=detail) from exc
    except APIStatusError as exc:
        logger.exception("Groq request failed with HTTP %s", exc.status_code)
        status_code = exc.status_code if exc.status_code in (401, 403, 503) else 502
        detail = (
            f"Groq rejected the request (HTTP {exc.status_code}). Check the "
            "GROQ_API_KEY and configured chat model."
        )
        if exc.status_code == 404:
            detail = (
                "The configured Groq chat model is unavailable to this account. "
                "Choose an active model enabled for your Groq account."
            )
        if exc.status_code == 503:
            detail = "Groq is temporarily unavailable. Please try again shortly."
        raise HTTPException(
            status_code=status_code,
            detail=detail,
        ) from exc
    except APIConnectionError as exc:
        logger.exception("Could not connect to Groq")
        raise HTTPException(
            status_code=503,
            detail="Could not connect to Groq. Check the network and try again.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected RAG failure")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while searching university documents.",
        ) from exc

    answer = response["answer"]
    retrieved_documents = response.get("context", [])
    session.add(
        ChatLog(
            conversation_id=conversation_id,
            user_id=current_user.id,
            language=request.language,
            message=request.message,
            answer=answer,
        )
    )
    try:
        await session.commit()
    except SQLAlchemyError as exc:
        await session.rollback()
        logger.exception("Could not save chat log for user %s", current_user.id)
        raise HTTPException(
            status_code=500,
            detail="The answer was generated but could not be saved to conversation history.",
        ) from exc

    sources_by_title = {
        citation.title: citation
        for citation in (_citation_from_document(doc) for doc in retrieved_documents)
    }
    grounded = bool(retrieved_documents) and not any(
        pattern.search(answer) for pattern in NOT_FOUND_PATTERNS
    )
    return ChatResponse(
        answer=answer,
        sources=list(sources_by_title.values()),
        confidence=None,
        grounded=grounded,
        conversation_id=conversation_id,
    )
