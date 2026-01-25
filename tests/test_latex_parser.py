"""Tests for LaTeX parser module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from arxiv2md.latex_parser import (
    convert_latex_to_markdown,
    detect_main_tex,
    extract_latex_metadata,
)


class TestDetectMainTex:
    """Tests for detect_main_tex function."""

    def test_finds_file_with_documentclass(self, tmp_path: Path) -> None:
        """File containing \\documentclass is detected as main file."""
        # Create files - main.tex has documentclass
        (tmp_path / "appendix.tex").write_text(r"\section{Appendix}")
        (tmp_path / "main.tex").write_text(
            r"\documentclass{article}" "\n" r"\begin{document}" "\n" r"\end{document}"
        )
        (tmp_path / "intro.tex").write_text(r"\section{Introduction}")

        result = detect_main_tex(tmp_path)

        assert result == tmp_path / "main.tex"

    def test_prefers_first_documentclass_alphabetically(self, tmp_path: Path) -> None:
        """When multiple files have \\documentclass, returns first alphabetically."""
        (tmp_path / "b_main.tex").write_text(r"\documentclass{article}")
        (tmp_path / "a_main.tex").write_text(r"\documentclass{report}")

        result = detect_main_tex(tmp_path)

        assert result == tmp_path / "a_main.tex"

    def test_falls_back_to_ms_tex(self, tmp_path: Path) -> None:
        """Falls back to ms.tex when no \\documentclass found."""
        (tmp_path / "appendix.tex").write_text(r"\section{Appendix}")
        (tmp_path / "ms.tex").write_text(r"\section{Main content}")
        (tmp_path / "intro.tex").write_text(r"\section{Introduction}")

        result = detect_main_tex(tmp_path)

        assert result == tmp_path / "ms.tex"

    def test_falls_back_to_alphabetically_first(self, tmp_path: Path) -> None:
        """Falls back to alphabetically first .tex file."""
        (tmp_path / "chapter2.tex").write_text(r"\section{Chapter 2}")
        (tmp_path / "chapter1.tex").write_text(r"\section{Chapter 1}")
        (tmp_path / "chapter3.tex").write_text(r"\section{Chapter 3}")

        result = detect_main_tex(tmp_path)

        assert result == tmp_path / "chapter1.tex"

    def test_raises_on_empty_directory(self, tmp_path: Path) -> None:
        """Raises ValueError when no .tex files exist."""
        with pytest.raises(ValueError, match="No .tex files found"):
            detect_main_tex(tmp_path)

    def test_raises_when_only_non_tex_files(self, tmp_path: Path) -> None:
        """Raises ValueError when directory has files but no .tex files."""
        (tmp_path / "readme.md").write_text("# README")
        (tmp_path / "figure.png").write_bytes(b"fake image")

        with pytest.raises(ValueError, match="No .tex files found"):
            detect_main_tex(tmp_path)

    def test_handles_encoding_errors(self, tmp_path: Path) -> None:
        """Handles files with invalid UTF-8 encoding gracefully."""
        (tmp_path / "main.tex").write_bytes(b"\xff\xfe" + b"\\documentclass{article}")
        (tmp_path / "other.tex").write_text(r"\section{Other}")

        # Should not raise, should find the documentclass despite encoding issues
        result = detect_main_tex(tmp_path)
        assert result == tmp_path / "main.tex"


class TestConvertLatexToMarkdown:
    """Tests for convert_latex_to_markdown function."""

    def test_converts_simple_latex(self, tmp_path: Path) -> None:
        """Converts basic LaTeX to Markdown."""
        tex_file = tmp_path / "test.tex"
        tex_file.write_text(
            r"\documentclass{article}"
            "\n"
            r"\begin{document}"
            "\n"
            r"\section{Hello}"
            "\n"
            "This is a test."
            "\n"
            r"\end{document}"
        )

        result = convert_latex_to_markdown(tex_file)

        assert "Hello" in result
        assert "This is a test." in result

    def test_preserves_math(self, tmp_path: Path) -> None:
        """Math expressions are preserved in output."""
        tex_file = tmp_path / "test.tex"
        tex_file.write_text(
            r"\documentclass{article}"
            "\n"
            r"\begin{document}"
            "\n"
            r"The equation $E = mc^2$ is famous."
            "\n"
            r"\end{document}"
        )

        result = convert_latex_to_markdown(tex_file)

        assert "E = mc^2" in result or "E=mc^2" in result

    def test_raises_when_pypandoc_missing(self, tmp_path: Path) -> None:
        """Raises RuntimeError when pypandoc is not installed."""
        tex_file = tmp_path / "test.tex"
        tex_file.write_text(r"\documentclass{article}")

        # Mock pypandoc import to raise ImportError
        import sys
        import builtins

        original_import = builtins.__import__

        def mock_import(name: str, *args, **kwargs):  # type: ignore[no-untyped-def]
            if name == "pypandoc":
                raise ImportError("No module named 'pypandoc'")
            return original_import(name, *args, **kwargs)

        # Remove pypandoc from cache and patch import
        sys.modules.pop("pypandoc", None)
        with patch.object(builtins, "__import__", side_effect=mock_import):
            with pytest.raises(RuntimeError, match="pypandoc_binary is required"):
                convert_latex_to_markdown(tex_file)

    def test_uses_wrap_none_argument(self, tmp_path: Path) -> None:
        """Verifies --wrap=none is passed to pandoc."""
        tex_file = tmp_path / "test.tex"
        tex_file.write_text(
            r"\documentclass{article}\begin{document}Test\end{document}"
        )

        mock_pypandoc = MagicMock()
        mock_pypandoc.convert_file.return_value = "Test"

        with patch.dict("sys.modules", {"pypandoc": mock_pypandoc}):
            # Re-import to use the mocked module
            from arxiv2md import latex_parser

            # Call through module to use patched import
            import importlib

            importlib.reload(latex_parser)
            latex_parser.convert_latex_to_markdown(tex_file)

            # Now uses filename only since we chdir to the source directory
            mock_pypandoc.convert_file.assert_called_once_with(
                tex_file.name,
                "markdown",
                format="latex",
                extra_args=["--wrap=none"],
            )


class TestExtractLatexMetadata:
    """Tests for extract_latex_metadata function."""

    def test_extracts_simple_title(self) -> None:
        """Extracts simple title."""
        tex = r"\title{A Simple Title}"

        result = extract_latex_metadata(tex)

        assert result["title"] == "A Simple Title"

    def test_extracts_title_with_formatting(self) -> None:
        """Extracts title with LaTeX formatting commands."""
        tex = r"\title{A \textbf{Bold} Title}"

        result = extract_latex_metadata(tex)

        assert result["title"] == "A Bold Title"

    def test_extracts_title_with_nested_braces(self) -> None:
        """Handles nested braces in title."""
        tex = r"\title{Title with {Nested} Braces}"

        result = extract_latex_metadata(tex)

        assert result["title"] == "Title with Nested Braces"

    def test_extracts_multiline_title(self) -> None:
        """Handles title spanning multiple lines."""
        tex = r"""\title{A Very Long Title
That Spans Multiple Lines}"""

        result = extract_latex_metadata(tex)

        assert "A Very Long Title" in result["title"]
        assert "Multiple Lines" in result["title"]

    def test_returns_none_for_missing_title(self) -> None:
        """Returns None when no title command found."""
        tex = r"\begin{document}Content\end{document}"

        result = extract_latex_metadata(tex)

        assert result["title"] is None

    def test_extracts_single_author(self) -> None:
        """Extracts single author name."""
        tex = r"\author{John Doe}"

        result = extract_latex_metadata(tex)

        assert result["authors"] == ["John Doe"]

    def test_extracts_multiple_authors_with_and(self) -> None:
        """Extracts multiple authors separated by \\and."""
        tex = r"\author{Alice Smith \and Bob Jones \and Carol White}"

        result = extract_latex_metadata(tex)

        assert result["authors"] == ["Alice Smith", "Bob Jones", "Carol White"]

    def test_handles_author_with_thanks(self) -> None:
        """Removes \\thanks{...} from author names."""
        tex = r"\author{John Doe\thanks{Corresponding author}}"

        result = extract_latex_metadata(tex)

        assert result["authors"] == ["John Doe"]

    def test_handles_author_with_inst(self) -> None:
        """Removes \\inst{...} from author names."""
        tex = r"\author{John Doe\inst{1} \and Jane Smith\inst{2}}"

        result = extract_latex_metadata(tex)

        assert result["authors"] == ["John Doe", "Jane Smith"]

    def test_handles_author_with_affiliation(self) -> None:
        """Removes \\affiliation{...} from author names."""
        tex = r"\author{John Doe\affiliation{MIT}}"

        result = extract_latex_metadata(tex)

        assert result["authors"] == ["John Doe"]

    def test_handles_author_with_email(self) -> None:
        """Removes \\email{...} from author names."""
        tex = r"\author{John Doe\email{john@example.com}}"

        result = extract_latex_metadata(tex)

        assert result["authors"] == ["John Doe"]

    def test_returns_empty_list_for_missing_author(self) -> None:
        """Returns empty list when no author command found."""
        tex = r"\title{A Title}"

        result = extract_latex_metadata(tex)

        assert result["authors"] == []

    def test_extracts_simple_abstract(self) -> None:
        """Extracts simple abstract text."""
        tex = r"\begin{abstract}This is the abstract.\end{abstract}"

        result = extract_latex_metadata(tex)

        assert result["abstract"] == "This is the abstract."

    def test_extracts_multiline_abstract(self) -> None:
        """Handles abstract spanning multiple lines."""
        tex = r"""\begin{abstract}
This is a longer abstract
that spans multiple lines
with various content.
\end{abstract}"""

        result = extract_latex_metadata(tex)

        assert "longer abstract" in result["abstract"]
        assert "multiple lines" in result["abstract"]

    def test_cleans_abstract_formatting(self) -> None:
        """Removes LaTeX formatting from abstract."""
        tex = r"\begin{abstract}This is \textbf{important} text.\end{abstract}"

        result = extract_latex_metadata(tex)

        assert result["abstract"] == "This is important text."

    def test_returns_none_for_missing_abstract(self) -> None:
        """Returns None when no abstract environment found."""
        tex = r"\title{A Title}\author{John}"

        result = extract_latex_metadata(tex)

        assert result["abstract"] is None

    def test_extracts_all_metadata(self) -> None:
        """Extracts title, authors, and abstract together."""
        tex = r"""
\documentclass{article}
\title{Complete Paper Title}
\author{Alice Author \and Bob Researcher}
\begin{document}
\begin{abstract}
This paper presents important findings.
\end{abstract}
\end{document}
"""

        result = extract_latex_metadata(tex)

        assert result["title"] == "Complete Paper Title"
        assert result["authors"] == ["Alice Author", "Bob Researcher"]
        assert result["abstract"] == "This paper presents important findings."

    def test_handles_latex_comments(self) -> None:
        """Strips LaTeX comments from content."""
        tex = r"""
\title{Title Here}  % This is a comment
\author{John Doe}
\begin{abstract}
% Comment at start of line
Abstract text here.
\end{abstract}
"""

        result = extract_latex_metadata(tex)

        assert "comment" not in result["title"].lower()
        assert result["abstract"] == "Abstract text here."

    def test_handles_complex_author_block(self) -> None:
        """Handles complex author blocks with multiple formatting commands."""
        tex = r"""
\author{
    John Doe\textsuperscript{1}\thanks{Equal contribution} \and
    Jane Smith\inst{2}\footnote{Corresponding author} \and
    Bob Wilson\affiliation{University}
}
"""

        result = extract_latex_metadata(tex)

        assert "John Doe" in result["authors"]
        assert "Jane Smith" in result["authors"]
        assert "Bob Wilson" in result["authors"]
        # Should not contain the footnote/thanks text
        assert not any("contribution" in a.lower() for a in result["authors"])

    def test_handles_empty_author(self) -> None:
        """Handles author command with empty or whitespace content."""
        tex = r"\author{   }"

        result = extract_latex_metadata(tex)

        assert result["authors"] == []

    def test_handles_deeply_nested_braces(self) -> None:
        """Handles deeply nested braces correctly."""
        tex = r"\title{A {title {with {deep} nesting}}}"

        result = extract_latex_metadata(tex)

        assert "deep" in result["title"]
        assert "nesting" in result["title"]
