import hashlib
import logging
from importlib import import_module
from pathlib import Path

import yaml
from langchain_core.documents import Document

try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False


def _import_symbol(module_name: str, symbol_name: str):
    try:
        module = import_module(module_name)
        return getattr(module, symbol_name)
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            f"Missing dependency: '{module_name}'. "
            "Install required packages with: "
            "pip install langchain-community langchain-groq "
            "langchain-huggingface sentence-transformers langchain-chroma "
            "langchain-text-splitters pypdf"
        ) from exc


PyPDFDirectoryLoader = _import_symbol("langchain_community.document_loaders", "PyPDFDirectoryLoader")
TextLoader = _import_symbol("langchain_community.document_loaders", "TextLoader")
RecursiveCharacterTextSplitter = _import_symbol("langchain_text_splitters", "RecursiveCharacterTextSplitter")
Chroma = _import_symbol("langchain_chroma", "Chroma")

if __package__:
    from .rag_core import load_embeddings
else:
    from rag_core import load_embeddings

PROJECT_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)
SCRAPED_DOCUMENTS_DIR = PROJECT_DIR.parent / "data" / "raw" / "scraped"
UPLOADED_DOCUMENTS_DIR = PROJECT_DIR.parent / "data" / "raw" / "uploaded"
SUPPORTED_DOCUMENT_EXTENSIONS = {".pdf", ".md", ".txt"}


def has_supported_documents(directory: Path) -> bool:
    return directory.is_dir() and any(
        path.suffix.lower() in SUPPORTED_DOCUMENT_EXTENSIONS
        for path in directory.rglob("*")
        if path.is_file()
    )


def _add_scraped_metadata(document: Document) -> None:
    source = Path(str(document.metadata.get("source", "")))
    if source.suffix.lower() != ".md" or not document.page_content.startswith("---"):
        return

    try:
        frontmatter = document.page_content.split("---", 2)[1]
        metadata = yaml.safe_load(frontmatter)
    except (IndexError, yaml.YAMLError):
        logger.warning("Could not parse scraped document metadata from %s", source)
        return

    if not isinstance(metadata, dict):
        return

    for source_key, target_key in (
        ("Document Type", "document_type"),
        ("Department", "department"),
    ):
        value = metadata.get(source_key)
        if isinstance(value, str) and value.strip():
            document.metadata[target_key] = value.strip().casefold()


load_dotenv(PROJECT_DIR / ".env")
DOCUMENTS_DIR = PROJECT_DIR / "university_docs"
if not has_supported_documents(DOCUMENTS_DIR):
    existing_documents_dir = PROJECT_DIR.parent / "venv" / "university_docs"
    if has_supported_documents(existing_documents_dir):
        DOCUMENTS_DIR = existing_documents_dir


def process_documents():
    logger.info("Loading source documents")
    managed_directories = (
        DOCUMENTS_DIR,
        SCRAPED_DOCUMENTS_DIR,
        UPLOADED_DOCUMENTS_DIR,
    )
    document_directories = [
        directory
        for directory in managed_directories
        if has_supported_documents(directory)
    ]

    raw_documents = []
    for source_directory in document_directories:
        logger.info("Reading supported documents from %s", source_directory)
        if any(
            path.suffix.lower() == ".pdf"
            for path in source_directory.rglob("*")
            if path.is_file()
        ):
            raw_documents.extend(PyPDFDirectoryLoader(str(source_directory)).load())
        for path in source_directory.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".md", ".txt"}:
                raw_documents.extend(TextLoader(str(path), encoding="utf-8").load())
    if SCRAPED_DOCUMENTS_DIR in document_directories:
        logger.info("Including scraped source documents")

    for document in raw_documents:
        _add_scraped_metadata(document)

    logger.info("Splitting documents into searchable chunks")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100
    )
    chunks = text_splitter.split_documents(raw_documents)
    logger.info("Updating the Chroma vector index")
    embeddings = load_embeddings()
    vectorstore = Chroma(
        persist_directory=str(PROJECT_DIR / "chroma_db_huggingface"),
        embedding_function=embeddings,
        collection_name="university_docs",
    )
    chunks_by_source = {}
    for chunk in chunks:
        source = str(Path(chunk.metadata["source"]).resolve())
        chunk.metadata["source"] = source
        chunks_by_source.setdefault(source, []).append(chunk)

    for source, source_chunks in chunks_by_source.items():
        chunk_ids = [
            hashlib.sha256(
                f"{source}\0{index}\0{chunk.page_content}".encode("utf-8")
            ).hexdigest()
            for index, chunk in enumerate(source_chunks)
        ]
        existing = vectorstore.get(where={"source": source}, include=[])
        existing_ids = set(existing["ids"])
        desired_ids = set(chunk_ids)
        updates = [
            (document_id, document)
            for document_id, document in zip(chunk_ids, source_chunks, strict=True)
            if document_id in existing_ids
        ]
        additions = [
            (document_id, document)
            for document_id, document in zip(chunk_ids, source_chunks, strict=True)
            if document_id not in existing_ids
        ]
        if updates:
            vectorstore.update_documents(
                ids=[document_id for document_id, _ in updates],
                documents=[document for _, document in updates],
            )
        if additions:
            vectorstore.add_documents(
                documents=[document for _, document in additions],
                ids=[document_id for document_id, _ in additions],
            )
        stale_ids = existing_ids - desired_ids
        if stale_ids:
            vectorstore.delete(ids=sorted(stale_ids))

    current_sources = set(chunks_by_source)
    indexed = vectorstore.get(include=["metadatas"])
    managed_roots = tuple(directory.resolve() for directory in managed_directories)
    stale_ids = [
        document_id
        for document_id, metadata in zip(
            indexed["ids"], indexed["metadatas"], strict=True
        )
        if metadata
        and metadata.get("source")
        and any(
            Path(str(metadata["source"])).resolve().is_relative_to(root)
            for root in managed_roots
        )
        and not Path(str(metadata["source"])).is_file()
    ]
    if stale_ids:
        vectorstore.delete(ids=stale_ids)
    logger.info(
        "Indexed %d source documents into %d chunks",
        len(current_sources),
        len(chunks),
    )
    return {
        "source_document_count": len(current_sources),
        "indexed_chunk_count": len(chunks),
    }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    process_documents()