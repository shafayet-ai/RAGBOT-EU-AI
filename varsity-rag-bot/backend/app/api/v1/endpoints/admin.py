import asyncio
import logging
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from ....core.database import get_db
from ....core.config import get_settings
from ....core.security import require_role
from ....models import ChatLog, User, UserRole
from ....schemas import (
    AdminDocument,
    AdminDocumentsResponse,
    AdminOverview,
    AdminUsersResponse,
    ReindexResponse,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_role([UserRole.ADMIN.value]))],
)
logger = logging.getLogger("eu_ai_admin")
PROJECT_ROOT = Path(__file__).resolve().parents[5]
UPLOAD_DIRECTORY = PROJECT_ROOT / "data" / "raw" / "uploaded"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".md", ".txt"}
_reindex_lock = asyncio.Lock()


def _list_documents() -> list[AdminDocument]:
    entries: list[AdminDocument] = []
    seen_paths: set[Path] = set()
    for directory in (
        PROJECT_ROOT / "root" / "university_docs",
        PROJECT_ROOT / "venv" / "university_docs",
        PROJECT_ROOT / "data" / "raw" / "scraped",
        UPLOAD_DIRECTORY,
    ):
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in ALLOWED_EXTENSIONS:
                continue
            resolved_path = path.resolve()
            if resolved_path in seen_paths:
                continue
            seen_paths.add(resolved_path)
            stat = path.stat()
            entries.append(
                AdminDocument(
                    filename=str(path.relative_to(PROJECT_ROOT)),
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc),
                    managed=directory.resolve() == UPLOAD_DIRECTORY.resolve(),
                )
            )
    return sorted(entries, key=lambda item: item.filename.casefold())


def _count_indexed_chunks() -> int:
    import chromadb

    client = chromadb.PersistentClient(
        path=str(PROJECT_ROOT / "root" / "chroma_db_huggingface")
    )
    return client.get_or_create_collection("university_docs").count()


def _run_reindex() -> dict[str, int]:
    from root.ingest import process_documents

    result = process_documents()
    return {
        "source_document_count": int(result["source_document_count"]),
        "indexed_chunk_count": int(result["indexed_chunk_count"]),
    }


def _resolve_managed_upload(filename: str) -> Path:
    candidate = (UPLOAD_DIRECTORY / filename).resolve()
    if candidate.parent != UPLOAD_DIRECTORY.resolve():
        raise HTTPException(status_code=400, detail="Invalid document filename.")
    return candidate


@router.get("/users", response_model=AdminUsersResponse)
async def list_users(
    session: Annotated[AsyncSession, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AdminUsersResponse:
    users = (
        await session.scalars(
            select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
        )
    ).all()
    total = await session.scalar(select(func.count()).select_from(User))
    return AdminUsersResponse(users=list(users), total=total or 0)


@router.get("/overview", response_model=AdminOverview)
async def get_overview(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminOverview:
    user_count = await session.scalar(select(func.count()).select_from(User))
    chat_count = await session.scalar(select(func.count()).select_from(ChatLog))
    try:
        indexed_chunks = await run_in_threadpool(_count_indexed_chunks)
    except Exception as exc:
        logger.exception("Could not read the vector index summary")
        raise HTTPException(
            status_code=503,
            detail="The vector index status is unavailable.",
        ) from exc
    documents = await run_in_threadpool(_list_documents)
    database_url = get_settings().database_url
    backend_name = (
        make_url(database_url).get_backend_name() if database_url else "unknown"
    )
    database_engine = {
        "postgresql": "PostgreSQL",
        "sqlite": "SQLite",
    }.get(backend_name, backend_name)
    return AdminOverview(
        application="EU-AI — Eastern University Knowledge Intelligence Assistant",
        application_version="1.0.0",
        python_version=platform.python_version(),
        rag_provider="Groq + Hugging Face",
        chat_model="qwen/qwen3.8-27b",
        embedding_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        vector_store="ChromaDB",
        database_engine=database_engine,
        database_status="connected",
        user_count=user_count or 0,
        chat_count=chat_count or 0,
        source_document_count=len(documents),
        indexed_chunk_count=indexed_chunks,
    )


@router.get("/documents", response_model=AdminDocumentsResponse)
async def list_documents() -> AdminDocumentsResponse:
    documents = await run_in_threadpool(_list_documents)
    return AdminDocumentsResponse(documents=documents, total=len(documents))


@router.post(
    "/documents",
    response_model=AdminDocument,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(file: Annotated[UploadFile, File()]) -> AdminDocument:
    original_name = Path(file.filename or "").name.strip()
    suffix = Path(original_name).suffix.lower()
    if not original_name or suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Only PDF, Markdown, and plain-text documents are supported.",
        )
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Document uploads are limited to 20 MiB.",
        )
    if not content:
        raise HTTPException(status_code=422, detail="The uploaded document is empty.")
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    target = _resolve_managed_upload(original_name)
    if target.exists():
        raise HTTPException(
            status_code=409,
            detail="A document with that filename already exists.",
        )
    try:
        async with _reindex_lock:
            target.write_bytes(content)
            result = await run_in_threadpool(_run_reindex)
    except Exception as exc:
        target.unlink(missing_ok=True)
        try:
            async with _reindex_lock:
                await run_in_threadpool(_run_reindex)
        except Exception:
            logger.exception("Could not clean up the vector index after upload failure")
        logger.exception("Document upload or indexing failed for %s", original_name)
        raise HTTPException(
            status_code=500,
            detail="The document could not be indexed. The upload was removed.",
        ) from exc
    stat = target.stat()
    logger.info(
        "Admin uploaded and indexed %s (%d chunks)",
        original_name,
        result["indexed_chunk_count"],
    )
    return AdminDocument(
        filename=str(target.relative_to(PROJECT_ROOT)),
        size_bytes=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc),
        managed=True,
    )


@router.delete("/documents/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(filename: str) -> None:
    if Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="Invalid document filename.")
    target = _resolve_managed_upload(filename)
    if target.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported document type.")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Uploaded document not found.")
    try:
        async with _reindex_lock:
            target.unlink()
            await run_in_threadpool(_run_reindex)
    except Exception as exc:
        logger.exception("Could not delete and re-index %s", filename)
        raise HTTPException(
            status_code=500,
            detail="The document was removed but re-indexing failed. Run re-index to repair the index.",
        ) from exc
    logger.info("Admin deleted document %s", filename)


@router.post("/reindex", response_model=ReindexResponse)
async def reindex_documents() -> ReindexResponse:
    try:
        async with _reindex_lock:
            result = await run_in_threadpool(_run_reindex)
    except Exception as exc:
        logger.exception("Admin requested re-index, but indexing failed")
        raise HTTPException(
            status_code=500,
            detail="Document re-indexing failed. Check the backend logs for details.",
        ) from exc
    return ReindexResponse(
        **result,
        message="Knowledge documents indexed successfully.",
    )
