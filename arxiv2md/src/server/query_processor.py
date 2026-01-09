"""Process a query by parsing input and generating a summary."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from arxiv2md.config import ARXIV2MD_CACHE_PATH
from arxiv2md.ingestion import ingest_paper
from arxiv2md.query_parser import parse_arxiv_input
from arxiv2md.utils.logging_config import get_logger
from server.models import IngestErrorResponse, IngestResponse, IngestSuccessResponse, PatternType
from server.server_config import MAX_DISPLAY_SIZE

# Initialize logger for this module
logger = get_logger(__name__)

if TYPE_CHECKING:
    from arxiv2md.schemas.query import ArxivQuery


def _store_digest_content(
    query: "ArxivQuery",
    digest_content: str,
) -> None:
    """Store digest content locally under the cache directory.

    Parameters
    ----------
    query : ArxivQuery
        The query object containing arXiv information.
    digest_content : str
        The complete digest content to store.

    """
    cache_dir = ARXIV2MD_CACHE_PATH / str(query.id)
    cache_dir.mkdir(parents=True, exist_ok=True)
    local_txt_file = cache_dir / "digest.txt"
    with local_txt_file.open("w", encoding="utf-8") as f:
        f.write(digest_content)


def _generate_digest_url(query: "ArxivQuery") -> str:
    """Generate the digest URL for the local cache.

    Parameters
    ----------
    query : IngestionQuery
        The query object containing repository information.

    Returns
    -------
    str
        The digest URL.

    """
    return f"/api/download/file/{query.id}"


async def process_query(
    input_text: str,
    *,
    remove_refs: bool = False,
    remove_toc: bool = False,
    remove_inline_citations: bool = False,
    section_filter_mode: str = "exclude",
    sections: list[str] | None = None,
    max_file_size: int | None = None,
    pattern_type: PatternType | None = None,
    pattern: str | None = None,
    token: str | None = None,
) -> IngestResponse:
    """Process an arXiv query and return a markdown summary."""
    if token:
        logger.info("Token provided but ignored for arXiv ingestion")

    try:
        query = parse_arxiv_input(input_text)
    except Exception as exc:
        logger.warning("Failed to parse arXiv input", extra={"input_text": input_text, "error": str(exc)})
        return IngestErrorResponse(error=str(exc))

    query = query.model_copy(
        update={
            "remove_refs": remove_refs,
            "remove_toc": remove_toc,
            "remove_inline_citations": remove_inline_citations,
            "section_filter_mode": section_filter_mode,
            "sections": sections or [],
        }
    )

    try:
        result, metadata = await ingest_paper(
            arxiv_id=query.arxiv_id,
            version=query.version,
            html_url=query.html_url,
            remove_refs=query.remove_refs,
            remove_toc=query.remove_toc,
            remove_inline_citations=query.remove_inline_citations,
            section_filter_mode=query.section_filter_mode,
            sections=query.sections,
        )
        summary = result.summary
        tree = result.sections_tree
        content = result.content
        digest_content = tree + "\n" + content
        _store_digest_content(query, digest_content)
    except Exception as exc:
        _print_error(query.html_url, exc, max_file_size, pattern_type, pattern)
        return IngestErrorResponse(error=f"{exc!s}")

    if len(content) > MAX_DISPLAY_SIZE:
        content = (
            f"(Content cropped to {int(MAX_DISPLAY_SIZE / 1_000)}k characters, "
            "download full ingest to see more)\n" + content[:MAX_DISPLAY_SIZE]
        )

    _print_success(
        url=query.html_url,
        max_file_size=max_file_size or 0,
        pattern_type=pattern_type or PatternType.EXCLUDE,
        pattern=pattern or "",
        summary=summary,
    )

    digest_url = _generate_digest_url(query)

    return IngestSuccessResponse(
        arxiv_id=query.arxiv_id,
        version=query.version,
        title=cast("str | None", metadata.get("title")),
        source_url=query.abs_url,
        summary=summary,
        digest_url=digest_url,
        tree=tree,
        sections_tree=tree,
        content=content,
        remove_refs=remove_refs,
        remove_toc=remove_toc,
        section_filter_mode=section_filter_mode,
        sections=query.sections,
    )


def _print_query(url: str, max_file_size: int, pattern_type: str, pattern: str) -> None:
    """Print a formatted summary of the query details for debugging.

    Parameters
    ----------
    url : str
        The URL associated with the query.
    max_file_size : int
        The maximum file size allowed for the query, in bytes.
    pattern_type : str
        Specifies the type of pattern to use, either "include" or "exclude".
    pattern : str
        The actual pattern string to include or exclude in the query.

    """
    logger.info(
        "Processing query",
        extra={
            "url": url,
            "max_file_size_kb": int(max_file_size / 1024) if max_file_size else 0,
            "pattern_type": pattern_type,
            "pattern": pattern,
        },
    )


def _print_error(url: str, exc: Exception, max_file_size: int | None, pattern_type: str, pattern: str) -> None:
    """Print a formatted error message for debugging.

    Parameters
    ----------
    url : str
        The URL associated with the query that caused the error.
    exc : Exception
        The exception raised during the query or process.
    max_file_size : int
        The maximum file size allowed for the query, in bytes.
    pattern_type : str
        Specifies the type of pattern to use, either "include" or "exclude".
    pattern : str
        The actual pattern string to include or exclude in the query.

    """
    max_file_size_kb = int(max_file_size / 1024) if max_file_size else 0
    logger.error(
        "Query processing failed",
        extra={
            "url": url,
            "max_file_size_kb": max_file_size_kb,
            "pattern_type": pattern_type,
            "pattern": pattern,
            "error": str(exc),
        },
    )


def _print_success(url: str, max_file_size: int | None, pattern_type: str, pattern: str, summary: str) -> None:
    """Print a formatted success message for debugging.

    Parameters
    ----------
    url : str
        The URL associated with the successful query.
    max_file_size : int
        The maximum file size allowed for the query, in bytes.
    pattern_type : str
        Specifies the type of pattern to use, either "include" or "exclude".
    pattern : str
        The actual pattern string to include or exclude in the query.
    summary : str
        A summary of the query result, including details like estimated tokens.

    """
    estimated_tokens = None
    token_marker = "Estimated tokens:"
    if token_marker in summary:
        estimated_tokens = summary.split(token_marker, 1)[1].strip().splitlines()[0].strip()
    logger.info(
        "Query processing completed successfully",
        extra={
            "url": url,
            "max_file_size_kb": int(max_file_size / 1024) if max_file_size else 0,
            "pattern_type": pattern_type,
            "pattern": pattern,
            "estimated_tokens": estimated_tokens,
        },
    )
