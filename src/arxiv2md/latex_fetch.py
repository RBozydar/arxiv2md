"""Fetch and cache arXiv LaTeX source bundles."""

from __future__ import annotations

import asyncio
import gzip
import shutil
import tarfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import httpx

from arxiv2md.config import (
    ARXIV2MD_CACHE_PATH,
    ARXIV2MD_CACHE_TTL_SECONDS,
    ARXIV2MD_FETCH_BACKOFF_S,
    ARXIV2MD_FETCH_MAX_RETRIES,
    ARXIV2MD_FETCH_TIMEOUT_S,
    ARXIV2MD_USER_AGENT,
)

_RETRY_STATUS = {429, 500, 502, 503, 504}
_ARXIV_EPRINT_URL = "https://arxiv.org/e-print"


async def fetch_arxiv_source(
    arxiv_id: str,
    version: str | None,
    *,
    use_cache: bool = True,
) -> Path:
    """Fetch and extract arXiv source bundle to cache directory.

    Args:
        arxiv_id: The arXiv paper ID (e.g., "2401.12345" or "2401.12345v1").
        version: Optional version string (e.g., "v1").
        use_cache: Whether to use cached source if available.

    Returns:
        Path to extracted directory containing source files (.tex, etc.).

    Raises:
        RuntimeError: If source bundle cannot be fetched or extracted.
    """
    cache_dir = _cache_dir_for(arxiv_id, version)
    source_dir = cache_dir / "source"
    marker_path = cache_dir / ".source_extracted"

    if use_cache and _is_cache_fresh(marker_path):
        return source_dir

    url = f"{_ARXIV_EPRINT_URL}/{arxiv_id}"
    source_bytes = await _fetch_source_with_retries(url)

    # Clean up old extraction if exists
    if source_dir.exists():
        shutil.rmtree(source_dir)
    source_dir.mkdir(parents=True, exist_ok=True)

    _extract_source_bundle(source_bytes, source_dir)

    # Write marker file to track cache freshness
    marker_path.write_text(datetime.now(timezone.utc).isoformat())

    return source_dir


async def _fetch_source_with_retries(url: str) -> bytes:
    """Fetch source bundle bytes with retry logic.

    Args:
        url: URL to fetch source bundle from.

    Returns:
        Raw bytes of the source bundle.

    Raises:
        RuntimeError: If fetch fails after all retries.
    """
    timeout = httpx.Timeout(ARXIV2MD_FETCH_TIMEOUT_S)
    headers = {"User-Agent": ARXIV2MD_USER_AGENT}
    last_exc: Exception | None = None

    for attempt in range(ARXIV2MD_FETCH_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(
                timeout=timeout, headers=headers, follow_redirects=True
            ) as client:
                response = await client.get(url)

            if response.status_code == 404:
                raise RuntimeError(
                    f"Source bundle not found at {url}. "
                    "The paper may not have source files available."
                )

            if response.status_code in _RETRY_STATUS:
                last_exc = RuntimeError(f"HTTP {response.status_code} from arXiv")
            else:
                response.raise_for_status()
                return response.content
        except (httpx.RequestError, httpx.HTTPStatusError, RuntimeError) as exc:
            last_exc = exc

        if attempt < ARXIV2MD_FETCH_MAX_RETRIES:
            backoff = ARXIV2MD_FETCH_BACKOFF_S * (2**attempt)
            await asyncio.sleep(backoff)

    raise RuntimeError(f"Failed to fetch source bundle from {url}: {last_exc}")


def _extract_source_bundle(data: bytes, dest_dir: Path) -> None:
    """Extract source bundle (tar.gz or gz) to destination directory.

    arXiv source bundles come in two formats:
    1. .tar.gz - Multiple files compressed as a tarball
    2. .gz - Single file (typically main.tex) gzipped

    Args:
        data: Raw bytes of the source bundle.
        dest_dir: Directory to extract files into.

    Raises:
        RuntimeError: If extraction fails or format is unrecognized.
    """
    # Try tar.gz first (most common)
    try:
        with tarfile.open(fileobj=BytesIO(data), mode="r:gz") as tar:
            # Security: filter out absolute paths and parent traversal
            safe_members = [
                m
                for m in tar.getmembers()
                if not m.name.startswith("/") and ".." not in m.name
            ]
            tar.extractall(dest_dir, members=safe_members)
            return
    except tarfile.TarError:
        pass

    # Try plain gzip (single file)
    try:
        decompressed = gzip.decompress(data)
        # Single file submissions are typically the main tex file
        output_path = dest_dir / "main.tex"
        output_path.write_bytes(decompressed)
        return
    except gzip.BadGzipFile:
        pass

    # If neither worked, the source might be uncompressed (rare)
    # Try to detect if it's plain text LaTeX
    try:
        text = data.decode("utf-8", errors="strict")
        if "\\documentclass" in text or "\\begin{document}" in text:
            output_path = dest_dir / "main.tex"
            output_path.write_text(text, encoding="utf-8")
            return
    except UnicodeDecodeError:
        pass

    raise RuntimeError(
        "Unable to extract source bundle. Expected tar.gz, gzip, or plain LaTeX format."
    )


def _is_cache_fresh(marker_path: Path) -> bool:
    """Check if cached source extraction is still fresh.

    Args:
        marker_path: Path to the cache marker file.

    Returns:
        True if cache is fresh and usable, False otherwise.
    """
    if not marker_path.exists():
        return False
    if ARXIV2MD_CACHE_TTL_SECONDS <= 0:
        return True
    mtime = datetime.fromtimestamp(marker_path.stat().st_mtime, tz=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - mtime).total_seconds()
    return age_seconds <= ARXIV2MD_CACHE_TTL_SECONDS


def _cache_dir_for(arxiv_id: str, version: str | None) -> Path:
    """Get cache directory path for a given arXiv paper.

    Uses the same directory structure as fetch.py for consistency,
    but stores source files in a 'source' subdirectory.

    Args:
        arxiv_id: The arXiv paper ID.
        version: Optional version string.

    Returns:
        Path to the cache directory for this paper.
    """
    base = arxiv_id
    if version and arxiv_id.endswith(version):
        base = arxiv_id[: -len(version)]
    version_tag = version or "latest"
    key = f"{base}__{version_tag}".replace("/", "_")
    return ARXIV2MD_CACHE_PATH / key
