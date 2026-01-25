"""Fetch and cache arXiv LaTeX source bundles."""

from __future__ import annotations

import asyncio
import gzip
import shutil
import tarfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Final

from arxiv2md.cache_utils import (
    cache_dir_for,
    is_cache_fresh,
    mkdir_async,
    write_text_async,
)
from arxiv2md.config import ARXIV2MD_CACHE_PATH, ARXIV2MD_CACHE_TTL_SECONDS
from arxiv2md.exceptions import ExtractionError, SourceNotAvailableError
from arxiv2md.http_utils import fetch_with_retries

_ARXIV_EPRINT_URL: Final[str] = "https://arxiv.org/e-print"

_404_MESSAGE = "Source bundle not found. The paper may not have source files available."


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
        SourceNotAvailableError: If source bundle is not available (404).
        FetchError: If source bundle cannot be fetched after retries.
        ExtractionError: If source bundle cannot be extracted.
    """
    cache_dir = cache_dir_for(arxiv_id, version, ARXIV2MD_CACHE_PATH)
    source_dir = cache_dir / "source"
    marker_path = cache_dir / ".source_extracted"

    if use_cache and is_cache_fresh(marker_path, ARXIV2MD_CACHE_TTL_SECONDS):
        return source_dir

    url = f"{_ARXIV_EPRINT_URL}/{arxiv_id}"
    source_bytes = await _fetch_source(url)

    # Clean up old extraction if exists - offload to thread
    if source_dir.exists():
        await asyncio.to_thread(shutil.rmtree, source_dir)
    await mkdir_async(source_dir, parents=True, exist_ok=True)

    # Extract in thread pool to avoid blocking
    await asyncio.to_thread(_extract_source_bundle, source_bytes, source_dir)

    # Write marker file to track cache freshness
    await write_text_async(marker_path, datetime.now(timezone.utc).isoformat())

    return source_dir


async def _fetch_source(url: str) -> bytes:
    """Fetch source bundle bytes from a URL.

    Args:
        url: URL to fetch source bundle from.

    Returns:
        Raw bytes of the source bundle.

    Raises:
        SourceNotAvailableError: If fetch returns 404.
        FetchError: If fetch fails after retries.
    """
    result = await fetch_with_retries(
        url,
        return_bytes=True,
        on_404=SourceNotAvailableError,
        on_404_message=_404_MESSAGE,
    )
    # Type narrowing: return_bytes=True means result is bytes
    if isinstance(result, str):
        return result.encode("utf-8")
    return result


def _extract_source_bundle(data: bytes, dest_dir: Path) -> None:
    """Extract source bundle (tar.gz or gz) to destination directory.

    arXiv source bundles come in two formats:
    1. .tar.gz - Multiple files compressed as a tarball
    2. .gz - Single file (typically main.tex) gzipped

    Args:
        data: Raw bytes of the source bundle.
        dest_dir: Directory to extract files into.

    Raises:
        ExtractionError: If extraction fails or format is unrecognized.
    """
    # Try tar.gz first (most common)
    try:
        with tarfile.open(fileobj=BytesIO(data), mode="r:gz") as tar:
            # Security: filter out absolute paths, parent traversal,
            # symlinks, hardlinks, and device files
            safe_members = [
                m
                for m in tar.getmembers()
                if not m.name.startswith("/")
                and ".." not in m.name
                and not m.issym()
                and not m.islnk()
                and not m.isdev()
            ]
            tar.extractall(dest_dir, members=safe_members, filter="data")
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

    raise ExtractionError(
        "Unable to extract source bundle. Expected tar.gz, gzip, or plain LaTeX format."
    )
