"""Fetch and cache arXiv HTML pages."""

from __future__ import annotations

import logging

import httpx

from arxiv2md.cache_utils import (
    cache_dir_for,
    is_cache_fresh,
    mkdir_async,
    read_text_async,
    write_text_async,
)
from arxiv2md.config import ARXIV2MD_CACHE_PATH, ARXIV2MD_CACHE_TTL_SECONDS
from arxiv2md.exceptions import FetchError, HTMLNotAvailableError
from arxiv2md.http_utils import fetch_with_retries

logger = logging.getLogger(__name__)

_404_MESSAGE = (
    "This paper does not have an HTML version available on arXiv. "
    "arxiv2md requires papers to be available in HTML format. "
    "Older papers may only be available as PDF."
)


async def fetch_arxiv_html(
    html_url: str,
    *,
    arxiv_id: str,
    version: str | None,
    use_cache: bool = True,
    ar5iv_url: str | None = None,
) -> str:
    """Fetch arXiv HTML and cache it locally.

    Tries html_url first (arxiv.org), then falls back to ar5iv_url if 404.

    Args:
        html_url: Primary URL to fetch HTML from (arxiv.org).
        arxiv_id: The arXiv paper ID.
        version: Optional version string.
        use_cache: Whether to use cached HTML if available.
        ar5iv_url: Optional fallback URL (ar5iv.org).

    Returns:
        The HTML content as a string.

    Raises:
        HTMLNotAvailableError: If HTML cannot be fetched from either URL.
        FetchError: If a network error occurs.
    """
    cache_dir = cache_dir_for(arxiv_id, version, ARXIV2MD_CACHE_PATH)
    html_path = cache_dir / "source.html"

    if use_cache and is_cache_fresh(html_path, ARXIV2MD_CACHE_TTL_SECONDS):
        return await read_text_async(html_path)

    # Try primary URL (arxiv.org) first
    try:
        html_text = await _fetch_html(html_url)
        await mkdir_async(cache_dir, parents=True, exist_ok=True)
        await write_text_async(html_path, html_text)
        return html_text
    except HTMLNotAvailableError as primary_error:
        # If we got 404 and have ar5iv fallback, try it
        if ar5iv_url:
            try:
                html_text = await _fetch_html(ar5iv_url)
                await mkdir_async(cache_dir, parents=True, exist_ok=True)
                await write_text_async(html_path, html_text)
                return html_text
            except (
                FetchError,
                httpx.RequestError,
                httpx.HTTPStatusError,
            ) as fallback_error:
                logger.debug(
                    "ar5iv fallback failed for %s: %s", ar5iv_url, fallback_error
                )
        # Re-raise the original error
        raise primary_error


async def _fetch_html(url: str) -> str:
    """Fetch HTML content from a URL.

    Args:
        url: URL to fetch HTML from.

    Returns:
        The HTML content as a string.

    Raises:
        HTMLNotAvailableError: If fetch returns 404.
        FetchError: If fetch fails after retries.
    """
    result = await fetch_with_retries(
        url,
        return_bytes=False,
        on_404=HTMLNotAvailableError,
        on_404_message=_404_MESSAGE,
    )
    # Type narrowing: return_bytes=False means result is str
    if isinstance(result, bytes):
        return result.decode("utf-8")
    return result
