"""Scrape selected Eastern University pages into RAG-ready Markdown files."""

from __future__ import annotations

import html
import json
import logging
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import html2text
import requests
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, HttpUrl
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

PROJECT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_DIR / "data" / "raw" / "scraped"
REQUEST_TIMEOUT = (10, 30)
REQUESTS_PER_SECOND_DELAY = 1.0
USER_AGENT = (
    "EasternUniversityRAGBot/1.0 (+https://www.easternuni.edu.bd/)"
)

logger = logging.getLogger("easternuni_scraper")


class ScrapeTarget(BaseModel):
    url: HttpUrl
    doc_type: Literal["admission", "curriculum", "faculty", "notice"]
    department: Literal["General", "CSE"]
    fallback_title: str


class ScrapedDocument(BaseModel):
    title: str
    source_url: str
    document_type: str
    department: str
    scraped_at: datetime
    content_language: Literal["English", "Bangla", "Mixed"]
    markdown: str


class ScrapeResult(BaseModel):
    url: str
    status: Literal["Success", "Failed", "Skipped"]
    output_path: Path | None = None
    detail: str | None = None


TARGETS = [
    ScrapeTarget(
        url="https://www.easternuni.edu.bd/admission",
        doc_type="admission",
        department="General",
        fallback_title="Admission",
    ),
    ScrapeTarget(
        url="https://www.easternuni.edu.bd/department-of-cse/bsc-in-cse/curriculum",
        doc_type="curriculum",
        department="CSE",
        fallback_title="BSc in CSE",
    ),
    ScrapeTarget(
        url="https://www.easternuni.edu.bd/department-of-cse/officials",
        doc_type="faculty",
        department="CSE",
        fallback_title="CSE Faculty and Officials",
    ),
    ScrapeTarget(
        url="https://www.easternuni.edu.bd/department-of-cse/notices",
        doc_type="notice",
        department="CSE",
        fallback_title="CSE Notices",
    ),
]

CONTENT_SELECTORS = (
    "article",
    "main",
    '[role="main"]',
    ".field-name-body",
    ".entry-content",
    ".page-content",
    ".main-content",
    "#content",
    ".content",
)
REMOVE_LAYOUT_RE = re.compile(
    r"(?:^|[\s_-])(?:sidebar|side-bar|breadcrumb|breadcrumbs|"
    r"site-header|site-footer|navigation|nav-menu|social-share)(?:$|[\s_-])",
    re.IGNORECASE,
)


def build_session() -> requests.Session:
    """Create an HTTP session with a descriptive user agent and bounded retries."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en,bn;q=0.9",
        }
    )
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_html(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "").lower()
    if content_type and "html" not in content_type:
        raise ValueError(f"Expected an HTML response, received {content_type!r}")
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def _is_layout_element(element: Tag) -> bool:
    attributes = [element.get("id", "")]
    classes = element.get("class", [])
    if isinstance(classes, list):
        attributes.extend(classes)
    return any(REMOVE_LAYOUT_RE.search(str(value)) for value in attributes)


def clean_and_extract(html_text: str) -> tuple[str, str]:
    """Remove non-content layout and return the page title and core HTML."""
    soup = BeautifulSoup(html_text, "html.parser")
    document_title = soup.find("title")
    fallback_title = document_title.get_text(" ", strip=True) if document_title else ""

    for element in soup.find_all(
        ["header", "footer", "nav", "script", "style", "iframe", "noscript", "aside"]
    ):
        element.decompose()
    for element in soup.find_all(True):
        if _is_layout_element(element):
            element.decompose()

    page_heading = soup.find("h1")
    content_root = None
    for selector in CONTENT_SELECTORS:
        candidates = soup.select(selector)
        if candidates:
            content_root = max(
                candidates, key=lambda candidate: len(candidate.get_text(" ", strip=True))
            )
            if content_root.get_text(" ", strip=True):
                break
            content_root = None

    if content_root is None:
        content_root = soup.body or soup

    heading = page_heading or content_root.find(["h1", "h2"])
    title = heading.get_text(" ", strip=True) if heading else fallback_title

    for element in content_root.find_all(["button", "input", "select", "textarea"]):
        element.decompose()
    return title, str(content_root)


def html_to_markdown(content_html: str) -> str:
    converter = html2text.HTML2Text()
    converter.body_width = 0
    converter.ignore_images = True
    converter.ignore_links = False
    converter.protect_links = True
    converter.unicode_snob = True
    return converter.handle(content_html).strip()


def detect_language(content: str) -> Literal["English", "Bangla", "Mixed"]:
    has_bangla = re.search(r"[\u0980-\u09ff]", content) is not None
    has_english = re.search(r"[A-Za-z]", content) is not None
    if has_bangla and has_english:
        return "Mixed"
    return "Bangla" if has_bangla else "English"


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_")
    return slug or "page"


def make_document(target: ScrapeTarget, title: str, markdown: str) -> ScrapedDocument:
    return ScrapedDocument(
        title=title or target.fallback_title,
        source_url=str(target.url),
        document_type=target.doc_type,
        department=target.department,
        scraped_at=datetime.now(timezone.utc),
        content_language=detect_language(markdown),
        markdown=markdown,
    )


def render_markdown(document: ScrapedDocument) -> str:
    metadata = (
        ("Document Title", document.title),
        ("Source URL", document.source_url),
        ("Document Type", document.document_type),
        ("Department", document.department),
        ("Scraping Date/Timestamp", document.scraped_at.isoformat()),
        ("Content Language", document.content_language),
    )
    frontmatter = "\n".join(
        f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in metadata
    )
    return f"---\n{frontmatter}\n---\n\n# {document.title}\n\n{document.markdown}\n"


def output_path_for(document: ScrapedDocument) -> Path:
    filename = "_".join(
        (
            slugify(document.department),
            slugify(document.document_type),
            slugify(document.title),
        )
    )
    return OUTPUT_DIR / f"{filename}.md"


def save_document(document: ScrapedDocument) -> Path:
    output_path = output_path_for(document)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(".md.tmp")
    temporary_path.write_text(render_markdown(document), encoding="utf-8")
    temporary_path.replace(output_path)
    return output_path


def scrape_target(session: requests.Session, target: ScrapeTarget) -> ScrapeResult:
    url = str(target.url)
    try:
        page_html = fetch_html(session, url)
        title, content_html = clean_and_extract(page_html)
        markdown = html_to_markdown(content_html)
        markdown = html.unescape(markdown).strip()
        if not markdown:
            detail = "No page content was found; no file was written."
            logger.warning("Skipped %s: %s", url, detail)
            return ScrapeResult(url=url, status="Skipped", detail=detail)

        document = make_document(target, title, markdown)
        output_path = save_document(document)
    except (requests.RequestException, OSError, ValueError) as exc:
        logger.exception("Failed to scrape %s", url)
        return ScrapeResult(url=url, status="Failed", detail=str(exc))

    logger.info("Success: %s -> %s", url, output_path)
    return ScrapeResult(url=url, status="Success", output_path=output_path)


def main() -> int:
    """Scrape all configured pages; return non-zero if any page failed."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    results: list[ScrapeResult] = []
    with build_session() as session:
        for index, target in enumerate(TARGETS):
            if index:
                time.sleep(REQUESTS_PER_SECOND_DELAY)
            results.append(scrape_target(session, target))

    successes = sum(result.status == "Success" for result in results)
    skipped = sum(result.status == "Skipped" for result in results)
    failed = sum(result.status == "Failed" for result in results)
    logger.info(
        "Scraping finished: %d succeeded, %d skipped, %d failed; output: %s",
        successes,
        skipped,
        failed,
        OUTPUT_DIR,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
