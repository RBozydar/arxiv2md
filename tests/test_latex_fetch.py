"""Tests for LaTeX source fetching module."""

from __future__ import annotations

import asyncio
import gzip
import io
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from arxiv2md.latex_fetch import (
    _extract_source_bundle,
    _is_cache_fresh,
    fetch_arxiv_source,
)


class TestFetchArxivSource:
    """Tests for fetch_arxiv_source function."""

    @pytest.mark.asyncio
    async def test_fetches_and_extracts_tar_gz_bundle(self, tmp_path: Path) -> None:
        """Successfully fetches and extracts a tar.gz source bundle."""
        # Create a tar.gz bundle with test content
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            main_tex = (
                b"\\documentclass{article}\n\\begin{document}\nHello\n\\end{document}"
            )
            info = tarfile.TarInfo(name="main.tex")
            info.size = len(main_tex)
            tar.addfile(info, io.BytesIO(main_tex))

            appendix_tex = b"\\section{Appendix}"
            info = tarfile.TarInfo(name="appendix.tex")
            info.size = len(appendix_tex)
            tar.addfile(info, io.BytesIO(appendix_tex))

        tar_bytes = tar_buffer.getvalue()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = tar_bytes
        mock_response.raise_for_status = MagicMock()

        with patch("arxiv2md.latex_fetch.ARXIV2MD_CACHE_PATH", tmp_path):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_class.return_value = mock_client

                result = await fetch_arxiv_source("2401.12345", "v1")

        assert result.exists()
        assert (result / "main.tex").exists()
        assert (result / "appendix.tex").exists()
        assert "documentclass" in (result / "main.tex").read_text()

    @pytest.mark.asyncio
    async def test_handles_single_gz_file(self, tmp_path: Path) -> None:
        """Successfully handles a single .gz compressed file."""
        # Create a gzipped single file
        tex_content = (
            b"\\documentclass{article}\n\\begin{document}\nSingle file\n\\end{document}"
        )
        gz_bytes = gzip.compress(tex_content)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = gz_bytes
        mock_response.raise_for_status = MagicMock()

        with patch("arxiv2md.latex_fetch.ARXIV2MD_CACHE_PATH", tmp_path):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_class.return_value = mock_client

                result = await fetch_arxiv_source("2401.12345", "v1")

        assert result.exists()
        assert (result / "main.tex").exists()
        assert "Single file" in (result / "main.tex").read_text()

    @pytest.mark.asyncio
    async def test_uses_cached_source_when_fresh(self, tmp_path: Path) -> None:
        """Uses cached source when cache is fresh."""
        arxiv_id = "2401.12345"
        version = "v1"

        # Set up cache directory structure
        # Note: arxiv_id does NOT end with version, so base = arxiv_id
        cache_key = f"{arxiv_id}__{version}".replace("/", "_")
        cache_dir = tmp_path / cache_key
        source_dir = cache_dir / "source"
        source_dir.mkdir(parents=True)
        marker_path = cache_dir / ".source_extracted"

        # Create cached files
        (source_dir / "main.tex").write_text("\\documentclass{article}")
        marker_path.write_text(datetime.now(timezone.utc).isoformat())

        with patch("arxiv2md.latex_fetch.ARXIV2MD_CACHE_PATH", tmp_path):
            with patch("arxiv2md.latex_fetch.ARXIV2MD_CACHE_TTL_SECONDS", 86400):
                with patch("httpx.AsyncClient") as mock_client_class:
                    result = await fetch_arxiv_source(arxiv_id, version, use_cache=True)

                    # Should not have made any HTTP requests
                    mock_client_class.assert_not_called()

        assert result == source_dir

    @pytest.mark.asyncio
    async def test_refetches_when_cache_stale(self, tmp_path: Path) -> None:
        """Refetches source when cache is stale."""
        import os
        import time

        arxiv_id = "2401.12345"
        version = "v1"

        # Set up stale cache
        # Note: arxiv_id does NOT end with version, so base = arxiv_id
        cache_key = f"{arxiv_id}__{version}".replace("/", "_")
        cache_dir = tmp_path / cache_key
        source_dir = cache_dir / "source"
        source_dir.mkdir(parents=True)
        marker_path = cache_dir / ".source_extracted"

        # Create cached files (old content)
        (source_dir / "main.tex").write_text("OLD CONTENT")
        marker_path.write_text("2020-01-01T00:00:00+00:00")

        # Set marker file mtime to be very old (cache staleness is based on mtime)
        old_time = time.time() - 100000
        os.utime(marker_path, (old_time, old_time))

        # Create fresh content to return
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            new_tex = b"\\documentclass{article}\nNEW CONTENT"
            info = tarfile.TarInfo(name="main.tex")
            info.size = len(new_tex)
            tar.addfile(info, io.BytesIO(new_tex))
        tar_bytes = tar_buffer.getvalue()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = tar_bytes
        mock_response.raise_for_status = MagicMock()

        with patch("arxiv2md.latex_fetch.ARXIV2MD_CACHE_PATH", tmp_path):
            with patch("arxiv2md.latex_fetch.ARXIV2MD_CACHE_TTL_SECONDS", 1):
                with patch("httpx.AsyncClient") as mock_client_class:
                    mock_client = AsyncMock()
                    mock_client.get = AsyncMock(return_value=mock_response)
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client_class.return_value = mock_client

                    result = await fetch_arxiv_source(arxiv_id, version, use_cache=True)

        assert "NEW CONTENT" in (result / "main.tex").read_text()

    @pytest.mark.asyncio
    async def test_bypasses_cache_when_disabled(self, tmp_path: Path) -> None:
        """Ignores cache when use_cache=False."""
        arxiv_id = "2401.12345"
        version = "v1"

        # Set up fresh cache that would normally be used
        cache_key = f"{arxiv_id[:-2]}__{version}".replace("/", "_")
        cache_dir = tmp_path / cache_key
        source_dir = cache_dir / "source"
        source_dir.mkdir(parents=True)
        marker_path = cache_dir / ".source_extracted"

        (source_dir / "main.tex").write_text("CACHED CONTENT")
        marker_path.write_text(datetime.now(timezone.utc).isoformat())

        # Create new content to return
        tex_content = b"\\documentclass{article}\nFRESH CONTENT"
        gz_bytes = gzip.compress(tex_content)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = gz_bytes
        mock_response.raise_for_status = MagicMock()

        with patch("arxiv2md.latex_fetch.ARXIV2MD_CACHE_PATH", tmp_path):
            with patch("arxiv2md.latex_fetch.ARXIV2MD_CACHE_TTL_SECONDS", 86400):
                with patch("httpx.AsyncClient") as mock_client_class:
                    mock_client = AsyncMock()
                    mock_client.get = AsyncMock(return_value=mock_response)
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client_class.return_value = mock_client

                    result = await fetch_arxiv_source(
                        arxiv_id, version, use_cache=False
                    )

                    # Should have made HTTP request despite cache being fresh
                    mock_client.get.assert_called_once()

        assert "FRESH CONTENT" in (result / "main.tex").read_text()

    @pytest.mark.asyncio
    async def test_retries_on_transient_failures(self, tmp_path: Path) -> None:
        """Retries fetch on transient HTTP errors."""
        tex_content = b"\\documentclass{article}"
        gz_bytes = gzip.compress(tex_content)

        # First two calls fail with 503, third succeeds
        fail_response = MagicMock()
        fail_response.status_code = 503
        fail_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "503 error", request=MagicMock(), response=fail_response
            )
        )

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.content = gz_bytes
        success_response.raise_for_status = MagicMock()

        with patch("arxiv2md.latex_fetch.ARXIV2MD_CACHE_PATH", tmp_path):
            with patch("arxiv2md.latex_fetch.ARXIV2MD_FETCH_MAX_RETRIES", 2):
                with patch("arxiv2md.latex_fetch.ARXIV2MD_FETCH_BACKOFF_S", 0.01):
                    with patch("httpx.AsyncClient") as mock_client_class:
                        mock_client = AsyncMock()
                        mock_client.get = AsyncMock(
                            side_effect=[fail_response, fail_response, success_response]
                        )
                        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                        mock_client.__aexit__ = AsyncMock(return_value=None)
                        mock_client_class.return_value = mock_client

                        result = await fetch_arxiv_source("2401.12345", "v1")

        assert result.exists()
        assert (result / "main.tex").exists()

    @pytest.mark.asyncio
    async def test_raises_on_404_response(self, tmp_path: Path) -> None:
        """Raises RuntimeError on 404 response after retries."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("arxiv2md.latex_fetch.ARXIV2MD_CACHE_PATH", tmp_path):
            with patch("arxiv2md.latex_fetch.ARXIV2MD_FETCH_MAX_RETRIES", 2):
                with patch("arxiv2md.latex_fetch.ARXIV2MD_FETCH_BACKOFF_S", 0.01):
                    with patch("httpx.AsyncClient") as mock_client_class:
                        mock_client = AsyncMock()
                        mock_client.get = AsyncMock(return_value=mock_response)
                        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                        mock_client.__aexit__ = AsyncMock(return_value=None)
                        mock_client_class.return_value = mock_client

                        with pytest.raises(
                            RuntimeError, match="Source bundle not found"
                        ):
                            await fetch_arxiv_source("nonexistent.12345", "v1")

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self, tmp_path: Path) -> None:
        """Raises RuntimeError after exhausting all retries."""
        fail_response = MagicMock()
        fail_response.status_code = 503
        fail_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "503 error", request=MagicMock(), response=fail_response
            )
        )

        with patch("arxiv2md.latex_fetch.ARXIV2MD_CACHE_PATH", tmp_path):
            with patch("arxiv2md.latex_fetch.ARXIV2MD_FETCH_MAX_RETRIES", 2):
                with patch("arxiv2md.latex_fetch.ARXIV2MD_FETCH_BACKOFF_S", 0.01):
                    with patch("httpx.AsyncClient") as mock_client_class:
                        mock_client = AsyncMock()
                        mock_client.get = AsyncMock(return_value=fail_response)
                        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                        mock_client.__aexit__ = AsyncMock(return_value=None)
                        mock_client_class.return_value = mock_client

                        with pytest.raises(
                            RuntimeError, match="Failed to fetch source bundle"
                        ):
                            await fetch_arxiv_source("2401.12345", "v1")

                        # Should have retried max_retries + 1 times total
                        assert mock_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_retries_on_request_error(self, tmp_path: Path) -> None:
        """Retries fetch on network request errors."""
        tex_content = b"\\documentclass{article}"
        gz_bytes = gzip.compress(tex_content)

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.content = gz_bytes
        success_response.raise_for_status = MagicMock()

        with patch("arxiv2md.latex_fetch.ARXIV2MD_CACHE_PATH", tmp_path):
            with patch("arxiv2md.latex_fetch.ARXIV2MD_FETCH_MAX_RETRIES", 2):
                with patch("arxiv2md.latex_fetch.ARXIV2MD_FETCH_BACKOFF_S", 0.01):
                    with patch("httpx.AsyncClient") as mock_client_class:
                        mock_client = AsyncMock()
                        mock_client.get = AsyncMock(
                            side_effect=[
                                httpx.RequestError("Connection failed"),
                                success_response,
                            ]
                        )
                        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                        mock_client.__aexit__ = AsyncMock(return_value=None)
                        mock_client_class.return_value = mock_client

                        result = await fetch_arxiv_source("2401.12345", "v1")

        assert result.exists()


class TestExtractSourceBundle:
    """Tests for _extract_source_bundle function."""

    def test_extracts_tar_gz(self, tmp_path: Path) -> None:
        """Extracts tar.gz bundles correctly."""
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            content = b"\\documentclass{article}"
            info = tarfile.TarInfo(name="paper.tex")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        tar_bytes = tar_buffer.getvalue()

        dest_dir = tmp_path / "extracted"
        dest_dir.mkdir()

        _extract_source_bundle(tar_bytes, dest_dir)

        assert (dest_dir / "paper.tex").exists()
        assert (dest_dir / "paper.tex").read_bytes() == content

    def test_extracts_plain_gz(self, tmp_path: Path) -> None:
        """Extracts plain gzip files (single file bundles)."""
        content = b"\\documentclass{article}\n\\begin{document}\n\\end{document}"
        gz_bytes = gzip.compress(content)

        dest_dir = tmp_path / "extracted"
        dest_dir.mkdir()

        _extract_source_bundle(gz_bytes, dest_dir)

        assert (dest_dir / "main.tex").exists()
        assert (dest_dir / "main.tex").read_bytes() == content

    def test_extracts_plain_latex(self, tmp_path: Path) -> None:
        """Handles uncompressed plain LaTeX content."""
        content = b"\\documentclass{article}\n\\begin{document}\nHello\n\\end{document}"

        dest_dir = tmp_path / "extracted"
        dest_dir.mkdir()

        _extract_source_bundle(content, dest_dir)

        assert (dest_dir / "main.tex").exists()
        assert (dest_dir / "main.tex").read_text() == content.decode("utf-8")

    def test_filters_unsafe_paths_in_tar(self, tmp_path: Path) -> None:
        """Filters out tar entries with unsafe paths."""
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            # Safe file
            safe_content = b"\\documentclass{article}"
            safe_info = tarfile.TarInfo(name="safe.tex")
            safe_info.size = len(safe_content)
            tar.addfile(safe_info, io.BytesIO(safe_content))

            # Unsafe: absolute path
            unsafe_info = tarfile.TarInfo(name="/etc/passwd")
            unsafe_info.size = 0
            tar.addfile(unsafe_info, io.BytesIO(b""))

            # Unsafe: parent traversal
            traversal_info = tarfile.TarInfo(name="../../../etc/shadow")
            traversal_info.size = 0
            tar.addfile(traversal_info, io.BytesIO(b""))
        tar_bytes = tar_buffer.getvalue()

        dest_dir = tmp_path / "extracted"
        dest_dir.mkdir()

        _extract_source_bundle(tar_bytes, dest_dir)

        # Safe file should exist
        assert (dest_dir / "safe.tex").exists()
        # Unsafe files should NOT have been extracted to dest_dir
        assert not (dest_dir / "etc" / "passwd").exists()
        assert not (dest_dir / "etc").exists()

    def test_raises_on_unrecognized_format(self, tmp_path: Path) -> None:
        """Raises RuntimeError for unrecognized bundle formats."""
        # Random binary data that's not valid tar, gzip, or LaTeX
        garbage_bytes = b"\x00\x01\x02\x03\x04\x05\x06\x07"

        dest_dir = tmp_path / "extracted"
        dest_dir.mkdir()

        with pytest.raises(RuntimeError, match="Unable to extract source bundle"):
            _extract_source_bundle(garbage_bytes, dest_dir)

    def test_extracts_nested_directories_in_tar(self, tmp_path: Path) -> None:
        """Handles tar.gz with nested directory structure."""
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            # Root file
            root_tex = b"\\documentclass{article}"
            root_info = tarfile.TarInfo(name="main.tex")
            root_info.size = len(root_tex)
            tar.addfile(root_info, io.BytesIO(root_tex))

            # Nested file
            nested_tex = b"\\section{Appendix}"
            nested_info = tarfile.TarInfo(name="sections/appendix.tex")
            nested_info.size = len(nested_tex)
            tar.addfile(nested_info, io.BytesIO(nested_tex))

            # Figure file
            figure_data = b"PNG DATA"
            figure_info = tarfile.TarInfo(name="figures/fig1.png")
            figure_info.size = len(figure_data)
            tar.addfile(figure_info, io.BytesIO(figure_data))
        tar_bytes = tar_buffer.getvalue()

        dest_dir = tmp_path / "extracted"
        dest_dir.mkdir()

        _extract_source_bundle(tar_bytes, dest_dir)

        assert (dest_dir / "main.tex").exists()
        assert (dest_dir / "sections" / "appendix.tex").exists()
        assert (dest_dir / "figures" / "fig1.png").exists()


class TestIsCacheFresh:
    """Tests for _is_cache_fresh function."""

    def test_returns_false_when_marker_missing(self, tmp_path: Path) -> None:
        """Returns False when marker file does not exist."""
        marker_path = tmp_path / ".source_extracted"

        assert not _is_cache_fresh(marker_path)

    def test_returns_true_when_marker_is_new(self, tmp_path: Path) -> None:
        """Returns True when marker file is within TTL."""
        marker_path = tmp_path / ".source_extracted"
        marker_path.write_text(datetime.now(timezone.utc).isoformat())

        with patch("arxiv2md.latex_fetch.ARXIV2MD_CACHE_TTL_SECONDS", 86400):
            assert _is_cache_fresh(marker_path)

    def test_returns_false_when_marker_is_stale(self, tmp_path: Path) -> None:
        """Returns False when marker file is older than TTL."""
        marker_path = tmp_path / ".source_extracted"
        marker_path.write_text("2020-01-01T00:00:00+00:00")

        # Force the marker to appear old via mtime
        import os
        import time

        old_time = time.time() - 100000  # Very old
        os.utime(marker_path, (old_time, old_time))

        with patch("arxiv2md.latex_fetch.ARXIV2MD_CACHE_TTL_SECONDS", 1):
            assert not _is_cache_fresh(marker_path)

    def test_returns_true_when_ttl_disabled(self, tmp_path: Path) -> None:
        """Returns True when TTL is set to 0 or negative (cache forever)."""
        marker_path = tmp_path / ".source_extracted"
        marker_path.write_text("2020-01-01T00:00:00+00:00")

        # Force the marker to appear old
        import os
        import time

        old_time = time.time() - 100000
        os.utime(marker_path, (old_time, old_time))

        with patch("arxiv2md.latex_fetch.ARXIV2MD_CACHE_TTL_SECONDS", 0):
            assert _is_cache_fresh(marker_path)

        with patch("arxiv2md.latex_fetch.ARXIV2MD_CACHE_TTL_SECONDS", -1):
            assert _is_cache_fresh(marker_path)
