"""Tests for ingestion fallback logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arxiv2md.exceptions import (
    FetchError,
    HTMLNotAvailableError,
    SourceNotAvailableError,
)
from arxiv2md.ingestion import IngestionOptions, ingest_paper


class TestIngestionFallback:
    """Tests for fallback behavior in ingest_paper."""

    @pytest.fixture
    def base_params(self) -> dict:
        """Base parameters for ingest_paper calls."""
        return {
            "arxiv_id": "2401.12345",
            "version": "v1",
            "html_url": "https://arxiv.org/html/2401.12345v1",
            "ar5iv_url": "https://ar5iv.labs.arxiv.org/html/2401.12345v1",
            "options": IngestionOptions(),
        }

    @pytest.fixture
    def mock_html_response(self) -> str:
        """Valid HTML response for parsing."""
        return """
        <html>
          <body>
            <article class="ltx_document">
              <h1 class="ltx_title ltx_title_document">Test Paper Title</h1>
              <div class="ltx_authors">
                <span class="ltx_text ltx_font_bold">Alice Author</span>
                <span class="ltx_text ltx_font_bold">Bob Researcher</span>
              </div>
              <div class="ltx_abstract">
                <p>This is the abstract text.</p>
              </div>
              <section class="ltx_section" id="S1">
                <h2 class="ltx_title ltx_title_section">1 Introduction</h2>
                <div class="ltx_para"><p>Introduction content.</p></div>
              </section>
            </article>
          </body>
        </html>
        """

    @pytest.mark.asyncio
    async def test_html_path_succeeds_no_fallback(
        self, base_params: dict, mock_html_response: str
    ) -> None:
        """When HTML fetch succeeds, no fallback is triggered."""
        with patch("arxiv2md.ingestion.fetch_arxiv_html") as mock_fetch:
            mock_fetch.return_value = mock_html_response

            with patch("arxiv2md.ingestion.fetch_arxiv_source") as mock_latex_fetch:
                result, metadata = await ingest_paper(**base_params)

                # LaTeX fetch should not be called
                mock_latex_fetch.assert_not_called()

        assert metadata["source"] == "html"
        assert metadata["title"] == "Test Paper Title"
        assert "Alice Author" in metadata["authors"]

    @pytest.mark.asyncio
    async def test_html_fails_latex_fallback_succeeds(
        self, base_params: dict, tmp_path: Path
    ) -> None:
        """When HTML fetch fails with 404, falls back to LaTeX."""
        html_error = HTMLNotAvailableError("2401.12345")

        # Set up mock LaTeX source directory
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        main_tex = source_dir / "main.tex"
        main_tex.write_text(
            r"""
\documentclass{article}
\title{LaTeX Paper Title}
\author{Charlie Coder \and Diana Dev}
\begin{document}
\begin{abstract}
This is the LaTeX abstract.
\end{abstract}
\section{Introduction}
Introduction from LaTeX.
\end{document}
"""
        )

        with patch("arxiv2md.ingestion.fetch_arxiv_html") as mock_fetch:
            mock_fetch.side_effect = html_error

            with patch("arxiv2md.ingestion.fetch_arxiv_source") as mock_latex_fetch:
                mock_latex_fetch.return_value = source_dir

                with patch(
                    "arxiv2md.ingestion.convert_latex_to_markdown"
                ) as mock_convert:
                    mock_convert.return_value = (
                        "# Introduction\n\nIntroduction from LaTeX."
                    )

                    result, metadata = await ingest_paper(**base_params)

        assert metadata["source"] == "latex"
        assert metadata["title"] == "LaTeX Paper Title"
        assert "Charlie Coder" in metadata["authors"]
        assert "Diana Dev" in metadata["authors"]
        assert "Introduction from LaTeX" in result.content

    @pytest.mark.asyncio
    async def test_both_html_and_latex_fail(
        self, base_params: dict, tmp_path: Path
    ) -> None:
        """When both HTML and LaTeX fail, raises appropriate error."""
        html_error = HTMLNotAvailableError("2401.12345")
        latex_error = SourceNotAvailableError("Source bundle not found")

        with patch("arxiv2md.ingestion.fetch_arxiv_html") as mock_html_fetch:
            mock_html_fetch.side_effect = html_error

            with patch("arxiv2md.ingestion.fetch_arxiv_source") as mock_latex_fetch:
                mock_latex_fetch.side_effect = latex_error

                with pytest.raises(
                    SourceNotAvailableError, match="Source bundle not found"
                ):
                    await ingest_paper(**base_params)

    @pytest.mark.asyncio
    async def test_force_latex_skips_html(
        self, base_params: dict, tmp_path: Path
    ) -> None:
        """When force_latex=True, HTML fetching is skipped entirely."""
        # Set up mock LaTeX source directory
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        main_tex = source_dir / "main.tex"
        main_tex.write_text(
            r"""
\documentclass{article}
\title{Forced LaTeX Title}
\author{Eve Engineer}
\begin{document}
\begin{abstract}
Forced LaTeX abstract.
\end{abstract}
\section{Content}
Main content.
\end{document}
"""
        )

        with patch("arxiv2md.ingestion.fetch_arxiv_html") as mock_html_fetch:
            with patch("arxiv2md.ingestion.fetch_arxiv_source") as mock_latex_fetch:
                mock_latex_fetch.return_value = source_dir

                with patch(
                    "arxiv2md.ingestion.convert_latex_to_markdown"
                ) as mock_convert:
                    mock_convert.return_value = "# Content\n\nMain content."

                    params = base_params.copy()
                    params["options"] = IngestionOptions(force_latex=True)
                    result, metadata = await ingest_paper(**params)

                    # HTML fetch should not be called at all
                    mock_html_fetch.assert_not_called()

        assert metadata["source"] == "latex"
        assert metadata["title"] == "Forced LaTeX Title"

    @pytest.mark.asyncio
    async def test_disable_latex_fallback_prevents_fallback(
        self, base_params: dict
    ) -> None:
        """When disable_latex_fallback=True, raises error instead of falling back."""
        html_error = HTMLNotAvailableError("2401.12345")

        with patch("arxiv2md.ingestion.fetch_arxiv_html") as mock_html_fetch:
            mock_html_fetch.side_effect = html_error

            with patch("arxiv2md.ingestion.fetch_arxiv_source") as mock_latex_fetch:
                with pytest.raises(HTMLNotAvailableError):
                    params = base_params.copy()
                    params["options"] = IngestionOptions(disable_latex_fallback=True)
                    await ingest_paper(**params)

                # LaTeX fetch should NOT be called
                mock_latex_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_404_html_error_raises_immediately(
        self, base_params: dict
    ) -> None:
        """Non-404 HTML errors are raised without triggering fallback."""
        network_error = FetchError("Connection timeout to arXiv server")

        with patch("arxiv2md.ingestion.fetch_arxiv_html") as mock_html_fetch:
            mock_html_fetch.side_effect = network_error

            with patch("arxiv2md.ingestion.fetch_arxiv_source") as mock_latex_fetch:
                with pytest.raises(FetchError, match="Connection timeout"):
                    await ingest_paper(**base_params)

                # Should not trigger LaTeX fallback for non-404 errors
                mock_latex_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_latex_fallback_includes_source_provenance(
        self, base_params: dict, tmp_path: Path
    ) -> None:
        """LaTeX fallback includes source provenance in output."""
        html_error = HTMLNotAvailableError("2401.12345")

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        main_tex = source_dir / "main.tex"
        main_tex.write_text(
            r"""
\documentclass{article}
\title{Provenance Test}
\author{Test Author}
\begin{document}
Content.
\end{document}
"""
        )

        with patch("arxiv2md.ingestion.fetch_arxiv_html") as mock_html_fetch:
            mock_html_fetch.side_effect = html_error

            with patch("arxiv2md.ingestion.fetch_arxiv_source") as mock_latex_fetch:
                mock_latex_fetch.return_value = source_dir

                with patch(
                    "arxiv2md.ingestion.convert_latex_to_markdown"
                ) as mock_convert:
                    mock_convert.return_value = "Content."

                    result, metadata = await ingest_paper(**base_params)

        # Verify source provenance in summary
        assert "Source: LaTeX (via Pandoc)" in result.summary

    @pytest.mark.asyncio
    async def test_latex_fallback_passes_version_correctly(
        self, base_params: dict, tmp_path: Path
    ) -> None:
        """Version is passed correctly to LaTeX fetch."""
        html_error = HTMLNotAvailableError("2401.12345")

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        main_tex = source_dir / "main.tex"
        main_tex.write_text(
            r"\documentclass{article}\begin{document}Test\end{document}"
        )

        with patch("arxiv2md.ingestion.fetch_arxiv_html") as mock_html_fetch:
            mock_html_fetch.side_effect = html_error

            with patch("arxiv2md.ingestion.fetch_arxiv_source") as mock_latex_fetch:
                mock_latex_fetch.return_value = source_dir

                with patch(
                    "arxiv2md.ingestion.convert_latex_to_markdown"
                ) as mock_convert:
                    mock_convert.return_value = "Test"

                    await ingest_paper(**base_params)

                    # Verify fetch was called with correct arxiv_id and version
                    mock_latex_fetch.assert_called_once_with("2401.12345", "v1")

    @pytest.mark.asyncio
    async def test_latex_fallback_handles_missing_metadata(
        self, base_params: dict, tmp_path: Path
    ) -> None:
        """LaTeX fallback handles missing title/author/abstract gracefully."""
        html_error = HTMLNotAvailableError("2401.12345")

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        main_tex = source_dir / "main.tex"
        # Minimal LaTeX without title/author/abstract
        main_tex.write_text(
            r"""
\documentclass{article}
\begin{document}
\section{Results}
Some results here.
\end{document}
"""
        )

        with patch("arxiv2md.ingestion.fetch_arxiv_html") as mock_html_fetch:
            mock_html_fetch.side_effect = html_error

            with patch("arxiv2md.ingestion.fetch_arxiv_source") as mock_latex_fetch:
                mock_latex_fetch.return_value = source_dir

                with patch(
                    "arxiv2md.ingestion.convert_latex_to_markdown"
                ) as mock_convert:
                    mock_convert.return_value = "# Results\n\nSome results here."

                    result, metadata = await ingest_paper(**base_params)

        # Should not crash, metadata fields should be None/empty
        assert metadata["title"] is None
        assert metadata["authors"] == []
        assert metadata["abstract"] is None
        assert "Results" in result.content

    @pytest.mark.asyncio
    async def test_latex_fallback_with_toc_disabled(
        self, base_params: dict, tmp_path: Path
    ) -> None:
        """LaTeX fallback respects remove_toc setting."""
        html_error = HTMLNotAvailableError("2401.12345")

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        main_tex = source_dir / "main.tex"
        main_tex.write_text(
            r"""
\documentclass{article}
\title{TOC Test}
\begin{document}
Content.
\end{document}
"""
        )

        with patch("arxiv2md.ingestion.fetch_arxiv_html") as mock_html_fetch:
            mock_html_fetch.side_effect = html_error

            with patch("arxiv2md.ingestion.fetch_arxiv_source") as mock_latex_fetch:
                mock_latex_fetch.return_value = source_dir

                with patch(
                    "arxiv2md.ingestion.convert_latex_to_markdown"
                ) as mock_convert:
                    mock_convert.return_value = "Content."

                    params = base_params.copy()
                    params["options"] = IngestionOptions(remove_toc=True)
                    result, metadata = await ingest_paper(**params)

        # Should not include TOC placeholder when remove_toc=True
        assert "## Contents" not in result.content

    @pytest.mark.asyncio
    async def test_latex_fallback_includes_abstract_in_content(
        self, base_params: dict, tmp_path: Path
    ) -> None:
        """LaTeX fallback includes abstract in content output."""
        html_error = HTMLNotAvailableError("2401.12345")

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        main_tex = source_dir / "main.tex"
        main_tex.write_text(
            r"""
\documentclass{article}
\title{Abstract Test}
\begin{document}
\begin{abstract}
This is a test abstract with important content.
\end{abstract}
\section{Body}
Body content.
\end{document}
"""
        )

        with patch("arxiv2md.ingestion.fetch_arxiv_html") as mock_html_fetch:
            mock_html_fetch.side_effect = html_error

            with patch("arxiv2md.ingestion.fetch_arxiv_source") as mock_latex_fetch:
                mock_latex_fetch.return_value = source_dir

                with patch(
                    "arxiv2md.ingestion.convert_latex_to_markdown"
                ) as mock_convert:
                    mock_convert.return_value = "# Body\n\nBody content."

                    result, metadata = await ingest_paper(**base_params)

        # Abstract should be in content
        assert "## Abstract" in result.content
        assert "important content" in result.content

    @pytest.mark.asyncio
    async def test_latex_parse_error_propagates(
        self, base_params: dict, tmp_path: Path
    ) -> None:
        """ParseError from detect_main_tex propagates correctly."""
        from arxiv2md.exceptions import ParseError

        html_error = HTMLNotAvailableError("2401.12345")

        # Create empty source directory
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        # No .tex files - will cause ParseError

        with patch("arxiv2md.ingestion.fetch_arxiv_html") as mock_html_fetch:
            mock_html_fetch.side_effect = html_error

            with patch("arxiv2md.ingestion.fetch_arxiv_source") as mock_latex_fetch:
                mock_latex_fetch.return_value = source_dir

                with pytest.raises(ParseError, match="No .tex files found"):
                    await ingest_paper(**base_params)
