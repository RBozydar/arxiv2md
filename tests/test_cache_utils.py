"""Tests for cache utilities module."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from arxiv2md.cache_utils import (
    cache_dir_for,
    is_cache_fresh,
    mkdir_async,
    read_text_async,
    write_text_async,
)


class TestIsCacheFresh:
    """Tests for is_cache_fresh function."""

    def test_returns_false_when_path_missing(self, tmp_path: Path) -> None:
        """Returns False when file does not exist."""
        path = tmp_path / "nonexistent"
        assert not is_cache_fresh(path, ttl_seconds=86400)

    def test_returns_true_when_file_is_new(self, tmp_path: Path) -> None:
        """Returns True when file is within TTL."""
        path = tmp_path / "cache_file"
        path.write_text("test content")

        assert is_cache_fresh(path, ttl_seconds=86400)

    def test_returns_false_when_file_is_old(self, tmp_path: Path) -> None:
        """Returns False when file is older than TTL."""
        path = tmp_path / "cache_file"
        path.write_text("test content")

        # Set mtime to be very old
        old_time = time.time() - 100000
        os.utime(path, (old_time, old_time))

        assert not is_cache_fresh(path, ttl_seconds=1)

    def test_returns_true_when_ttl_is_zero(self, tmp_path: Path) -> None:
        """Returns True when TTL is 0 (cache forever)."""
        path = tmp_path / "cache_file"
        path.write_text("test content")

        # Set mtime to be very old
        old_time = time.time() - 100000
        os.utime(path, (old_time, old_time))

        assert is_cache_fresh(path, ttl_seconds=0)

    def test_returns_true_when_ttl_is_negative(self, tmp_path: Path) -> None:
        """Returns True when TTL is negative (cache forever)."""
        path = tmp_path / "cache_file"
        path.write_text("test content")

        # Set mtime to be very old
        old_time = time.time() - 100000
        os.utime(path, (old_time, old_time))

        assert is_cache_fresh(path, ttl_seconds=-1)


class TestCacheDirFor:
    """Tests for cache_dir_for function."""

    def test_basic_id_and_version(self, tmp_path: Path) -> None:
        """Generates correct path for basic ID and version."""
        result = cache_dir_for("2401.12345", "v1", tmp_path)
        assert result == tmp_path / "2401.12345__v1"

    def test_id_ending_with_version(self, tmp_path: Path) -> None:
        """Strips version suffix from ID when it matches version."""
        result = cache_dir_for("2401.12345v1", "v1", tmp_path)
        assert result == tmp_path / "2401.12345__v1"

    def test_latest_version_when_none(self, tmp_path: Path) -> None:
        """Uses 'latest' when version is None."""
        result = cache_dir_for("2401.12345", None, tmp_path)
        assert result == tmp_path / "2401.12345__latest"

    def test_old_format_id_with_slash(self, tmp_path: Path) -> None:
        """Replaces slashes with underscores for old format IDs."""
        result = cache_dir_for("cs/9901001", "v2", tmp_path)
        assert result == tmp_path / "cs_9901001__v2"

    def test_old_format_id_with_version_suffix(self, tmp_path: Path) -> None:
        """Handles old format ID with version suffix correctly."""
        result = cache_dir_for("cs/9901001v2", "v2", tmp_path)
        assert result == tmp_path / "cs_9901001__v2"


class TestReadTextAsync:
    """Tests for read_text_async function."""

    @pytest.mark.asyncio
    async def test_reads_text_content(self, tmp_path: Path) -> None:
        """Reads text content from file."""
        path = tmp_path / "test.txt"
        path.write_text("Hello, World!", encoding="utf-8")

        result = await read_text_async(path)

        assert result == "Hello, World!"

    @pytest.mark.asyncio
    async def test_respects_encoding(self, tmp_path: Path) -> None:
        """Respects specified encoding."""
        path = tmp_path / "test.txt"
        content = "Cafe"
        path.write_text(content, encoding="latin-1")

        result = await read_text_async(path, encoding="latin-1")

        assert result == content


class TestWriteTextAsync:
    """Tests for write_text_async function."""

    @pytest.mark.asyncio
    async def test_writes_text_content(self, tmp_path: Path) -> None:
        """Writes text content to file."""
        path = tmp_path / "test.txt"

        await write_text_async(path, "Hello, World!")

        assert path.read_text(encoding="utf-8") == "Hello, World!"

    @pytest.mark.asyncio
    async def test_respects_encoding(self, tmp_path: Path) -> None:
        """Respects specified encoding."""
        path = tmp_path / "test.txt"

        await write_text_async(path, "Cafe", encoding="latin-1")

        assert path.read_text(encoding="latin-1") == "Cafe"


class TestMkdirAsync:
    """Tests for mkdir_async function."""

    @pytest.mark.asyncio
    async def test_creates_directory(self, tmp_path: Path) -> None:
        """Creates a new directory."""
        path = tmp_path / "new_dir"

        await mkdir_async(path)

        assert path.exists()
        assert path.is_dir()

    @pytest.mark.asyncio
    async def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Creates parent directories when parents=True."""
        path = tmp_path / "a" / "b" / "c"

        await mkdir_async(path, parents=True)

        assert path.exists()
        assert path.is_dir()

    @pytest.mark.asyncio
    async def test_raises_when_parents_not_exist(self, tmp_path: Path) -> None:
        """Raises when parents don't exist and parents=False."""
        path = tmp_path / "a" / "b" / "c"

        with pytest.raises(FileNotFoundError):
            await mkdir_async(path)

    @pytest.mark.asyncio
    async def test_exists_ok_ignores_existing(self, tmp_path: Path) -> None:
        """Does not raise when directory exists and exist_ok=True."""
        path = tmp_path / "existing"
        path.mkdir()

        # Should not raise
        await mkdir_async(path, exist_ok=True)

        assert path.exists()

    @pytest.mark.asyncio
    async def test_raises_when_exists_and_not_ok(self, tmp_path: Path) -> None:
        """Raises when directory exists and exist_ok=False."""
        path = tmp_path / "existing"
        path.mkdir()

        with pytest.raises(FileExistsError):
            await mkdir_async(path)
