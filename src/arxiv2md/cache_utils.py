"""Cache utilities for managing local file caching."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path


def is_cache_fresh(path: Path, ttl_seconds: int) -> bool:
    """Check if a cached file is still fresh based on its modification time.

    Args:
        path: Path to the cached file or marker file.
        ttl_seconds: Time-to-live in seconds. If <= 0, cache is considered
            fresh indefinitely (cache forever mode).

    Returns:
        True if the cache is fresh and usable, False otherwise.
    """
    if not path.exists():
        return False
    if ttl_seconds <= 0:
        return True
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - mtime).total_seconds()
    return age_seconds <= ttl_seconds


def cache_dir_for(arxiv_id: str, version: str | None, base_path: Path) -> Path:
    """Get the cache directory path for a given arXiv paper.

    The directory structure uses a consistent naming scheme that combines
    the paper ID and version into a safe filename.

    Args:
        arxiv_id: The arXiv paper ID (e.g., "2401.12345" or "2401.12345v1").
        version: Optional version string (e.g., "v1").
        base_path: The base cache directory path.

    Returns:
        Path to the cache directory for this paper version.
    """
    base = arxiv_id
    if version and arxiv_id.endswith(version):
        base = arxiv_id[: -len(version)]
    version_tag = version or "latest"
    key = f"{base}__{version_tag}".replace("/", "_")
    return base_path / key


async def read_text_async(path: Path, encoding: str = "utf-8") -> str:
    """Read text from a file asynchronously using a thread pool.

    Args:
        path: Path to the file to read.
        encoding: Text encoding to use.

    Returns:
        The file contents as a string.
    """
    return await asyncio.to_thread(path.read_text, encoding=encoding)


async def write_text_async(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write text to a file asynchronously using a thread pool.

    Args:
        path: Path to the file to write.
        content: Text content to write.
        encoding: Text encoding to use.
    """
    await asyncio.to_thread(path.write_text, content, encoding=encoding)


async def mkdir_async(
    path: Path, parents: bool = False, exist_ok: bool = False
) -> None:
    """Create a directory asynchronously using a thread pool.

    Args:
        path: Path to the directory to create.
        parents: If True, create parent directories as needed.
        exist_ok: If True, don't raise an error if directory exists.
    """
    await asyncio.to_thread(path.mkdir, parents=parents, exist_ok=exist_ok)
