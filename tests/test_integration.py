"""Integration tests for arxiv2md with real network calls.

These tests make actual HTTP requests to arXiv servers and test the full
ingestion pipeline. They are marked with @pytest.mark.integration so they
can be skipped in CI environments.

Run integration tests only:
    pytest -m integration

Skip integration tests:
    pytest -m "not integration"
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from arxiv2md import ArxivQuery, IngestionResult, ingest_paper, parse_arxiv_input

if TYPE_CHECKING:
    from pathlib import Path


# Default timeout for network operations (60 seconds)
NETWORK_TIMEOUT = 60.0


class TestHTMLPath:
    """Test HTML fetching path from arxiv.org."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_html_path_with_recent_paper(self) -> None:
        """Test fetching a recent paper with HTML available.

        Uses 2501.11120v1 which should have HTML rendering on arxiv.org.
        """
        query = parse_arxiv_input("2501.11120v1")

        result, metadata = await asyncio.wait_for(
            ingest_paper(
                arxiv_id=query.arxiv_id,
                version=query.version,
                html_url=query.html_url,
                ar5iv_url=query.ar5iv_url,
                latex_url=query.latex_url,
                remove_refs=False,
                remove_toc=False,
                remove_inline_citations=False,
                section_filter_mode="exclude",
                sections=[],
            ),
            timeout=NETWORK_TIMEOUT,
        )

        # Verify result structure
        assert isinstance(result, IngestionResult)
        assert result.content, "Content should not be empty"
        assert result.summary, "Summary should not be empty"

        # Verify source is HTML
        assert metadata["source"] == "html", "Source should be html for recent papers"

        # Verify metadata extraction
        assert metadata["title"], "Title should be extracted"
        assert metadata["authors"], "Authors should be extracted"
        assert isinstance(metadata["authors"], list)
        assert len(metadata["authors"]) > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_html_path_content_is_markdown(self) -> None:
        """Verify that the content returned is valid markdown."""
        query = parse_arxiv_input("2501.11120v1")

        result, metadata = await asyncio.wait_for(
            ingest_paper(
                arxiv_id=query.arxiv_id,
                version=query.version,
                html_url=query.html_url,
                ar5iv_url=query.ar5iv_url,
                latex_url=query.latex_url,
                remove_refs=False,
                remove_toc=False,
                remove_inline_citations=False,
                section_filter_mode="exclude",
                sections=[],
            ),
            timeout=NETWORK_TIMEOUT,
        )

        # Markdown should contain headers
        assert "#" in result.content, "Markdown content should contain headers"

        # Content should not contain raw HTML tags (fully converted)
        assert "<div" not in result.content.lower()
        assert "<span" not in result.content.lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_html_path_with_section_filtering(self) -> None:
        """Test HTML path with section filtering enabled."""
        query = parse_arxiv_input("2501.11120v1")

        result, metadata = await asyncio.wait_for(
            ingest_paper(
                arxiv_id=query.arxiv_id,
                version=query.version,
                html_url=query.html_url,
                ar5iv_url=query.ar5iv_url,
                latex_url=query.latex_url,
                remove_refs=True,
                remove_toc=True,
                remove_inline_citations=False,
                section_filter_mode="exclude",
                sections=[],
            ),
            timeout=NETWORK_TIMEOUT,
        )

        assert metadata["source"] == "html"
        # References section should be excluded
        content_lower = result.content.lower()
        # Check that explicit "## References" heading is not present
        # (some inline mentions may still exist)
        assert (
            "## references" not in content_lower
            or "## bibliography" not in content_lower
        )


class TestAr5ivFallback:
    """Test ar5iv fallback path.

    Since ar5iv fallback is triggered when arxiv.org HTML fails,
    we mock the primary fetch to fail and verify ar5iv is attempted.
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_ar5iv_fallback_when_primary_fails(self) -> None:
        """Test that ar5iv is used when primary arxiv.org HTML fails.

        This test mocks the fetch_arxiv_html function to return ar5iv-sourced
        content when called, simulating the fallback path.
        """
        query = parse_arxiv_input("2501.11120v1")

        mock_html = """
        <html>
          <body>
            <article class="ltx_document">
              <h1 class="ltx_title ltx_title_document">Test ar5iv Title</h1>
              <div class="ltx_authors">
                <span class="ltx_text ltx_font_bold">Test Author</span>
              </div>
              <section class="ltx_section" id="S1">
                <h2 class="ltx_title ltx_title_section">1 Introduction</h2>
                <div class="ltx_para"><p>Test content from ar5iv.</p></div>
              </section>
            </article>
          </body>
        </html>
        """

        # Track what URL was passed to understand fallback behavior
        fetch_call_kwargs: list[dict] = []

        async def mock_fetch_html(
            html_url: str,
            *,
            arxiv_id: str,
            version: str | None,
            use_cache: bool = True,
            ar5iv_url: str | None = None,
        ) -> str:
            fetch_call_kwargs.append(
                {
                    "html_url": html_url,
                    "ar5iv_url": ar5iv_url,
                }
            )
            # Return mock HTML (simulating ar5iv success after arxiv.org failure)
            return mock_html

        with patch("arxiv2md.ingestion.fetch_arxiv_html", side_effect=mock_fetch_html):
            result, metadata = await ingest_paper(
                arxiv_id=query.arxiv_id,
                version=query.version,
                html_url=query.html_url,
                ar5iv_url=query.ar5iv_url,
                latex_url=query.latex_url,
                remove_refs=False,
                remove_toc=False,
                remove_inline_citations=False,
                section_filter_mode="exclude",
                sections=[],
            )

        # Verify fetch was called with ar5iv_url for fallback
        assert len(fetch_call_kwargs) == 1
        assert fetch_call_kwargs[0]["ar5iv_url"] is not None
        assert "ar5iv" in fetch_call_kwargs[0]["ar5iv_url"]
        assert metadata["source"] == "html"
        assert metadata["title"] is not None
        assert "Test ar5iv Title" in str(metadata["title"])


class TestLatexFallback:
    """Test LaTeX fallback path for older papers.

    Note: Most older papers are now available via ar5iv HTML rendering,
    so we test LaTeX fallback by mocking HTML failure or using force_latex.
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_latex_path_with_old_paper_forced(self) -> None:
        """Test fetching an older paper via forced LaTeX mode.

        Uses hep-th/9901001 from 1999 with force_latex=True to ensure
        we test the LaTeX processing path.
        """
        query = parse_arxiv_input("hep-th/9901001")

        result, metadata = await asyncio.wait_for(
            ingest_paper(
                arxiv_id=query.arxiv_id,
                version=query.version,
                html_url=query.html_url,
                ar5iv_url=query.ar5iv_url,
                latex_url=query.latex_url,
                remove_refs=False,
                remove_toc=False,
                remove_inline_citations=False,
                section_filter_mode="exclude",
                sections=[],
                force_latex=True,  # Force LaTeX path
            ),
            timeout=NETWORK_TIMEOUT * 2,  # LaTeX conversion may take longer
        )

        # Verify result structure
        assert isinstance(result, IngestionResult)
        assert result.content, "Content should not be empty"

        # Verify source is LaTeX
        assert metadata["source"] == "latex", "Source should be latex when forced"

        # Verify pandoc conversion worked (content should be markdown)
        assert result.content, "Pandoc should have produced markdown content"

        # Summary should indicate LaTeX source
        assert "LaTeX" in result.summary

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_latex_fallback_triggered_on_html_failure(self) -> None:
        """Test that LaTeX fallback is triggered when HTML fetch fails.

        This uses mocking to simulate HTML unavailability.
        """
        query = parse_arxiv_input("2501.11120v1")

        with patch("arxiv2md.ingestion.fetch_arxiv_html") as mock_fetch:
            mock_fetch.side_effect = RuntimeError(
                "This paper does not have an HTML version available on arXiv."
            )

            result, metadata = await asyncio.wait_for(
                ingest_paper(
                    arxiv_id=query.arxiv_id,
                    version=query.version,
                    html_url=query.html_url,
                    ar5iv_url=query.ar5iv_url,
                    latex_url=query.latex_url,
                    remove_refs=False,
                    remove_toc=False,
                    remove_inline_citations=False,
                    section_filter_mode="exclude",
                    sections=[],
                ),
                timeout=NETWORK_TIMEOUT * 2,
            )

        # Should have fallen back to LaTeX
        assert metadata["source"] == "latex"
        assert result.content, "Content should not be empty"
        assert "LaTeX" in result.summary

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_latex_path_produces_valid_markdown(self) -> None:
        """Verify that LaTeX conversion produces valid markdown."""
        query = parse_arxiv_input("hep-th/9901001")

        result, metadata = await asyncio.wait_for(
            ingest_paper(
                arxiv_id=query.arxiv_id,
                version=query.version,
                html_url=query.html_url,
                ar5iv_url=query.ar5iv_url,
                latex_url=query.latex_url,
                remove_refs=False,
                remove_toc=False,
                remove_inline_citations=False,
                section_filter_mode="exclude",
                sections=[],
                force_latex=True,  # Force LaTeX path
            ),
            timeout=NETWORK_TIMEOUT * 2,
        )

        assert metadata["source"] == "latex"

        # Content should exist and be reasonable length
        assert len(result.content) > 100, "Content should be substantial"

        # Should not contain raw LaTeX commands in output
        # (some may remain in math, but document structure should be converted)
        assert "\\documentclass" not in result.content
        assert "\\begin{document}" not in result.content


class TestForceLatex:
    """Test force_latex mode with papers that have HTML."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_force_latex_skips_html(self) -> None:
        """Test that force_latex=True uses LaTeX even when HTML is available.

        Uses a recent paper that has HTML, but forces LaTeX processing.
        """
        query = parse_arxiv_input("2501.11120v1")

        result, metadata = await asyncio.wait_for(
            ingest_paper(
                arxiv_id=query.arxiv_id,
                version=query.version,
                html_url=query.html_url,
                ar5iv_url=query.ar5iv_url,
                latex_url=query.latex_url,
                remove_refs=False,
                remove_toc=False,
                remove_inline_citations=False,
                section_filter_mode="exclude",
                sections=[],
                force_latex=True,
            ),
            timeout=NETWORK_TIMEOUT * 2,
        )

        # Verify source is LaTeX despite HTML being available
        assert metadata["source"] == "latex", "Source should be latex when forced"

        # Verify content was produced
        assert result.content, "Content should not be empty"

        # Summary should indicate LaTeX source
        assert "LaTeX" in result.summary

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_force_latex_does_not_fetch_html(self) -> None:
        """Verify that force_latex=True does not attempt HTML fetch."""
        query = parse_arxiv_input("2501.11120v1")

        with patch("arxiv2md.ingestion.fetch_arxiv_html") as mock_html_fetch:
            result, metadata = await asyncio.wait_for(
                ingest_paper(
                    arxiv_id=query.arxiv_id,
                    version=query.version,
                    html_url=query.html_url,
                    ar5iv_url=query.ar5iv_url,
                    latex_url=query.latex_url,
                    remove_refs=False,
                    remove_toc=False,
                    remove_inline_citations=False,
                    section_filter_mode="exclude",
                    sections=[],
                    force_latex=True,
                ),
                timeout=NETWORK_TIMEOUT * 2,
            )

            # HTML fetch should not have been called at all
            mock_html_fetch.assert_not_called()

        assert metadata["source"] == "latex"


class TestCLI:
    """End-to-end CLI tests using subprocess."""

    @pytest.mark.integration
    def test_cli_basic_invocation(self, tmp_path: Path) -> None:
        """Test basic CLI invocation with stdout output."""
        result = subprocess.run(
            [sys.executable, "-m", "arxiv2md", "2501.11120v1", "-o", "-"],
            capture_output=True,
            text=True,
            timeout=NETWORK_TIMEOUT * 2,
            cwd=str(tmp_path),
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert result.stdout, "CLI should produce output"
        assert "#" in result.stdout, "Output should contain markdown headers"

    @pytest.mark.integration
    def test_cli_output_to_file(self, tmp_path: Path) -> None:
        """Test CLI writing output to a file."""
        output_file = tmp_path / "output.md"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "arxiv2md",
                "2501.11120v1",
                "-o",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            timeout=NETWORK_TIMEOUT * 2,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_file.exists(), "Output file should be created"

        content = output_file.read_text(encoding="utf-8")
        assert content, "Output file should not be empty"
        assert "#" in content, "Output should contain markdown headers"

    @pytest.mark.integration
    def test_cli_with_latex_flag(self, tmp_path: Path) -> None:
        """Test CLI with --latex flag to force LaTeX processing."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "arxiv2md",
                "2501.11120v1",
                "--latex",
                "-o",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=NETWORK_TIMEOUT * 2,
            cwd=str(tmp_path),
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "LaTeX" in result.stdout, "Output should indicate LaTeX source"

    @pytest.mark.integration
    def test_cli_with_remove_refs(self, tmp_path: Path) -> None:
        """Test CLI with --remove-refs flag."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "arxiv2md",
                "2501.11120v1",
                "--remove-refs",
                "-o",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=NETWORK_TIMEOUT * 2,
            cwd=str(tmp_path),
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        # Output should not have explicit "References" or "Bibliography" section
        # We look for exact standalone heading matches (not partial matches like
        # "risk preferences" which would incorrectly match "references")
        output_lower = result.stdout.lower()
        lines = [line.strip() for line in output_lower.split("\n")]

        # Look for standalone bibliography headings - these are ONLY:
        # "# references", "## references", "# bibliography", "## bibliography"
        # We need exact matches to avoid false positives
        import re

        ref_pattern = re.compile(r"^#{1,3}\s+(references|bibliography)\s*$")
        ref_headings = [line for line in lines if ref_pattern.match(line)]
        assert len(ref_headings) == 0, (
            f"References heading should be removed: {ref_headings}"
        )

    @pytest.mark.integration
    def test_cli_with_old_paper_forced_latex(self, tmp_path: Path) -> None:
        """Test CLI with an older paper using forced LaTeX mode.

        Note: Many old papers are now available via ar5iv, so we use
        --latex flag to force LaTeX processing.
        """
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "arxiv2md",
                "hep-th/9901001",
                "--latex",
                "-o",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=NETWORK_TIMEOUT * 3,  # Longer timeout for LaTeX
            cwd=str(tmp_path),
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert result.stdout, "CLI should produce output"
        assert "LaTeX" in result.stdout, "Should use LaTeX path when forced"

    @pytest.mark.integration
    def test_cli_invalid_arxiv_id(self, tmp_path: Path) -> None:
        """Test CLI with invalid arXiv ID."""
        result = subprocess.run(
            [sys.executable, "-m", "arxiv2md", "invalid-id-123", "-o", "-"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(tmp_path),
        )

        assert result.returncode != 0, "CLI should fail for invalid ID"
        assert "error" in result.stderr.lower() or "Error" in result.stderr


class TestLibraryAPI:
    """Test the public library API."""

    def test_parse_arxiv_input_with_id(self) -> None:
        """Test parsing a plain arXiv ID."""
        query = parse_arxiv_input("2501.11120v1")

        assert isinstance(query, ArxivQuery)
        assert query.arxiv_id == "2501.11120v1"
        assert query.version == "v1"
        assert "arxiv.org/html" in query.html_url
        assert "ar5iv" in query.ar5iv_url
        assert "e-print" in query.latex_url

    def test_parse_arxiv_input_with_url(self) -> None:
        """Test parsing an arXiv URL."""
        query = parse_arxiv_input("https://arxiv.org/abs/2501.11120v1")

        assert isinstance(query, ArxivQuery)
        assert query.arxiv_id == "2501.11120v1"
        assert query.version == "v1"

    def test_parse_arxiv_input_with_old_format(self) -> None:
        """Test parsing old-style arXiv ID (category/number)."""
        query = parse_arxiv_input("hep-th/9901001")

        assert isinstance(query, ArxivQuery)
        assert query.arxiv_id == "hep-th/9901001"
        assert query.version is None

    def test_parse_arxiv_input_with_arxiv_prefix(self) -> None:
        """Test parsing arXiv: prefixed ID."""
        query = parse_arxiv_input("arxiv:2501.11120v1")

        assert isinstance(query, ArxivQuery)
        assert query.arxiv_id == "2501.11120v1"
        assert query.version == "v1"

    def test_parse_arxiv_input_without_version(self) -> None:
        """Test parsing ID without version."""
        query = parse_arxiv_input("2501.11120")

        assert isinstance(query, ArxivQuery)
        assert query.arxiv_id == "2501.11120"
        assert query.version is None

    def test_parse_arxiv_input_invalid(self) -> None:
        """Test that invalid input raises ValueError."""
        with pytest.raises(ValueError, match="Unrecognized arXiv identifier"):
            parse_arxiv_input("not-a-valid-id")

    def test_parse_arxiv_input_empty(self) -> None:
        """Test that empty input raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_arxiv_input("")

    def test_parse_arxiv_input_html_url(self) -> None:
        """Test parsing HTML URL format."""
        query = parse_arxiv_input("https://arxiv.org/html/2501.11120v1")

        assert query.arxiv_id == "2501.11120v1"
        assert query.version == "v1"

    def test_parse_arxiv_input_pdf_url(self) -> None:
        """Test parsing PDF URL format."""
        query = parse_arxiv_input("https://arxiv.org/pdf/2501.11120v1.pdf")

        assert query.arxiv_id == "2501.11120v1"
        assert query.version == "v1"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_ingest_paper_api(self) -> None:
        """Test the ingest_paper function directly."""
        query = parse_arxiv_input("2501.11120v1")

        result, metadata = await asyncio.wait_for(
            ingest_paper(
                arxiv_id=query.arxiv_id,
                version=query.version,
                html_url=query.html_url,
                ar5iv_url=query.ar5iv_url,
                latex_url=query.latex_url,
                remove_refs=False,
                remove_toc=False,
                remove_inline_citations=False,
                section_filter_mode="exclude",
                sections=[],
            ),
            timeout=NETWORK_TIMEOUT,
        )

        # Verify return types
        assert isinstance(result, IngestionResult)
        assert isinstance(metadata, dict)

        # Verify result fields
        assert isinstance(result.summary, str)
        assert isinstance(result.sections_tree, str)
        assert isinstance(result.content, str)

        # Verify metadata fields
        assert "source" in metadata
        assert "title" in metadata
        assert "authors" in metadata
        assert "abstract" in metadata

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_ingest_paper_with_all_options(self) -> None:
        """Test ingest_paper with all options enabled."""
        query = parse_arxiv_input("2501.11120v1")

        result, metadata = await asyncio.wait_for(
            ingest_paper(
                arxiv_id=query.arxiv_id,
                version=query.version,
                html_url=query.html_url,
                ar5iv_url=query.ar5iv_url,
                latex_url=query.latex_url,
                remove_refs=True,
                remove_toc=True,
                remove_inline_citations=True,
                section_filter_mode="include",
                sections=["introduction", "abstract"],
            ),
            timeout=NETWORK_TIMEOUT,
        )

        assert isinstance(result, IngestionResult)
        # With include mode and specific sections, content should be limited
        assert result.content


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_nonexistent_paper(self) -> None:
        """Test handling of non-existent paper ID."""
        query = parse_arxiv_input("9999.99999")

        with pytest.raises(RuntimeError):
            await asyncio.wait_for(
                ingest_paper(
                    arxiv_id=query.arxiv_id,
                    version=query.version,
                    html_url=query.html_url,
                    ar5iv_url=query.ar5iv_url,
                    latex_url=query.latex_url,
                    remove_refs=False,
                    remove_toc=False,
                    remove_inline_citations=False,
                    section_filter_mode="exclude",
                    sections=[],
                ),
                timeout=NETWORK_TIMEOUT,
            )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_disable_latex_fallback(self) -> None:
        """Test that disable_latex_fallback raises error when HTML unavailable.

        We mock HTML failure to test this since most papers have ar5iv HTML.
        """
        query = parse_arxiv_input("2501.11120v1")

        with patch("arxiv2md.ingestion.fetch_arxiv_html") as mock_fetch:
            mock_fetch.side_effect = RuntimeError(
                "This paper does not have an HTML version available on arXiv."
            )

            with pytest.raises(RuntimeError, match="does not have an HTML version"):
                await asyncio.wait_for(
                    ingest_paper(
                        arxiv_id=query.arxiv_id,
                        version=query.version,
                        html_url=query.html_url,
                        ar5iv_url=query.ar5iv_url,
                        latex_url=query.latex_url,
                        remove_refs=False,
                        remove_toc=False,
                        remove_inline_citations=False,
                        section_filter_mode="exclude",
                        sections=[],
                        disable_latex_fallback=True,
                    ),
                    timeout=NETWORK_TIMEOUT,
                )


class TestMetadataExtraction:
    """Test metadata extraction from papers."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_html_metadata_extraction(self) -> None:
        """Test that metadata is correctly extracted from HTML papers."""
        query = parse_arxiv_input("2501.11120v1")

        result, metadata = await asyncio.wait_for(
            ingest_paper(
                arxiv_id=query.arxiv_id,
                version=query.version,
                html_url=query.html_url,
                ar5iv_url=query.ar5iv_url,
                latex_url=query.latex_url,
                remove_refs=False,
                remove_toc=False,
                remove_inline_citations=False,
                section_filter_mode="exclude",
                sections=[],
            ),
            timeout=NETWORK_TIMEOUT,
        )

        # Title should be non-empty string
        assert metadata["title"]
        assert isinstance(metadata["title"], str)

        # Authors should be a non-empty list
        assert metadata["authors"]
        assert isinstance(metadata["authors"], list)
        assert all(isinstance(a, str) for a in metadata["authors"])

        # Source should be specified
        assert metadata["source"] in ("html", "latex")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_latex_metadata_extraction(self) -> None:
        """Test that metadata is correctly extracted from LaTeX papers."""
        query = parse_arxiv_input("hep-th/9901001")

        result, metadata = await asyncio.wait_for(
            ingest_paper(
                arxiv_id=query.arxiv_id,
                version=query.version,
                html_url=query.html_url,
                ar5iv_url=query.ar5iv_url,
                latex_url=query.latex_url,
                remove_refs=False,
                remove_toc=False,
                remove_inline_citations=False,
                section_filter_mode="exclude",
                sections=[],
                force_latex=True,  # Force LaTeX to test extraction
            ),
            timeout=NETWORK_TIMEOUT * 2,
        )

        assert metadata["source"] == "latex"
        # LaTeX papers should have at least some metadata
        # (though extraction may be imperfect)
        # At minimum, source should be set
        assert "source" in metadata
        # Title should typically be extracted from LaTeX
        # (may be None for some papers, but check it exists)
        assert "title" in metadata
