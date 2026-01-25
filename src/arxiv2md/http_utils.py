"""HTTP utilities for fetching content with retry logic and connection pooling."""

from __future__ import annotations

import asyncio
from typing import Final

import httpx

from arxiv2md.config import (
    ARXIV2MD_FETCH_BACKOFF_S,
    ARXIV2MD_FETCH_MAX_RETRIES,
    ARXIV2MD_FETCH_TIMEOUT_S,
    ARXIV2MD_USER_AGENT,
)
from arxiv2md.exceptions import FetchError

RETRY_STATUS_CODES: Final[frozenset[int]] = frozenset({429, 500, 502, 503, 504})

_MAX_REDIRECTS: Final[int] = 5


async def fetch_with_retries(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    return_bytes: bool = False,
    on_404: type[Exception] | None = None,
    on_404_message: str | None = None,
) -> str | bytes:
    """Fetch content from a URL with retry logic for transient failures.

    Args:
        url: The URL to fetch.
        client: Optional httpx.AsyncClient for connection pooling. If not
            provided, a new client is created for this request.
        return_bytes: If True, return raw bytes instead of decoded text.
        on_404: Custom exception class to raise on 404. Defaults to FetchError.
        on_404_message: Custom error message for 404 responses. If None,
            a generic message is used.

    Returns:
        The fetched content as a string (default) or bytes (if return_bytes=True).

    Raises:
        FetchError (or custom on_404 exception): If the fetch fails after all
            retries or returns 404.
    """
    timeout = httpx.Timeout(ARXIV2MD_FETCH_TIMEOUT_S)
    headers = {"User-Agent": ARXIV2MD_USER_AGENT}
    last_exc: Exception | None = None
    not_found_exc_class = on_404 or FetchError

    async def do_fetch(http_client: httpx.AsyncClient) -> str | bytes:
        nonlocal last_exc

        for attempt in range(ARXIV2MD_FETCH_MAX_RETRIES + 1):
            try:
                response = await http_client.get(url)

                if response.status_code == 404:
                    message = on_404_message or f"Resource not found at {url}"
                    raise not_found_exc_class(message)

                if response.status_code in RETRY_STATUS_CODES:
                    last_exc = FetchError(f"HTTP {response.status_code} from {url}")
                else:
                    response.raise_for_status()
                    return response.content if return_bytes else response.text
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                last_exc = exc
            except not_found_exc_class:
                raise

            if attempt < ARXIV2MD_FETCH_MAX_RETRIES:
                backoff = ARXIV2MD_FETCH_BACKOFF_S * (2**attempt)
                await asyncio.sleep(backoff)

        raise FetchError(f"Failed to fetch {url}: {last_exc}")

    if client is not None:
        return await do_fetch(client)

    async with httpx.AsyncClient(
        timeout=timeout,
        headers=headers,
        follow_redirects=True,
        max_redirects=_MAX_REDIRECTS,
    ) as new_client:
        return await do_fetch(new_client)
