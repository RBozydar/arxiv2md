"""Parse LaTeX source files and convert to Markdown."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from arxiv2md.exceptions import ConversionError, ParseError


def detect_main_tex(source_dir: Path) -> Path:
    """Find the main .tex file in an arXiv source bundle.

    Detection order (based on arXiv AutoTeX behavior):
    1. File containing \\documentclass directive
    2. File named 'ms.tex' (arXiv convention)
    3. Alphabetically first .tex file

    Args:
        source_dir: Directory containing extracted LaTeX source files.

    Returns:
        Path to the main .tex file.

    Raises:
        ParseError: If no .tex files are found in the directory.
    """
    tex_files = sorted(source_dir.glob("*.tex"))
    if not tex_files:
        raise ParseError(f"No .tex files found in {source_dir}")

    # Look for file containing \documentclass
    for tex_file in tex_files:
        content = tex_file.read_text(errors="replace")
        if r"\documentclass" in content:
            return tex_file

    # Fall back to ms.tex if it exists
    ms_tex = source_dir / "ms.tex"
    if ms_tex.exists():
        return ms_tex

    # Fall back to alphabetically first .tex file
    return tex_files[0]


def convert_latex_to_markdown(main_tex: Path) -> str:
    """Convert LaTeX file to Markdown using pandoc (sync version).

    Uses subprocess with explicit cwd parameter instead of os.chdir()
    to be thread-safe. Pandoc resolves \\input{} paths relative to cwd.

    Args:
        main_tex: Path to the main .tex file.

    Returns:
        Markdown string converted from LaTeX source.

    Raises:
        ConversionError: If pandoc is not available or conversion fails.
    """
    source_dir = main_tex.parent.resolve()
    tex_filename = main_tex.name

    result = subprocess.run(
        ["pandoc", tex_filename, "-f", "latex", "-t", "markdown", "--wrap=none"],
        cwd=source_dir,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise ConversionError(f"Pandoc conversion failed: {result.stderr}")

    return result.stdout


def extract_latex_metadata(tex_content: str) -> dict[str, str | list[str] | None]:
    """Extract title, authors, and abstract from LaTeX preamble.

    Args:
        tex_content: Raw LaTeX source content.

    Returns:
        Dictionary with keys:
        - title: Paper title or None
        - authors: List of author names (may be empty)
        - abstract: Abstract text or None
    """
    return {
        "title": _extract_title(tex_content),
        "authors": _extract_authors(tex_content),
        "abstract": _extract_abstract(tex_content),
    }


def _extract_braced_content(text: str, start_pos: int) -> str | None:
    """Extract content within matched braces starting at given position.

    Handles nested braces correctly by counting brace depth.

    Args:
        text: Full text to search.
        start_pos: Position where opening brace '{' is expected.

    Returns:
        Content between matched braces, or None if no match found.
    """
    if start_pos >= len(text) or text[start_pos] != "{":
        return None

    depth = 0
    content_start = start_pos + 1
    for i in range(start_pos, len(text)):
        char = text[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[content_start:i]
    return None


def _extract_title(tex_content: str) -> str | None:
    """Extract title from \\title{...} command."""
    match = re.search(r"\\title\s*\{", tex_content)
    if not match:
        return None

    content = _extract_braced_content(tex_content, match.end() - 1)
    if content is None:
        return None

    return _clean_latex_text(content)


def _extract_authors(tex_content: str) -> list[str]:
    """Extract authors from \\author{...} command.

    Handles \\and separators and common LaTeX author formatting.
    """
    match = re.search(r"\\author\s*\{", tex_content)
    if not match:
        return []

    content = _extract_braced_content(tex_content, match.end() - 1)
    if content is None:
        return []

    # Split on \and (with optional surrounding whitespace)
    raw_authors = re.split(r"\\and\b", content)

    authors: list[str] = []
    for raw in raw_authors:
        cleaned = _clean_author_entry(raw)
        if cleaned:
            authors.append(cleaned)

    return authors


def _clean_author_entry(raw: str) -> str | None:
    """Clean a single author entry from LaTeX markup."""
    # Remove common LaTeX commands in author blocks
    text = raw

    # Remove \thanks{...} footnotes
    text = _remove_command_with_braces(text, "thanks")
    # Remove \inst{...} institution markers
    text = _remove_command_with_braces(text, "inst")
    # Remove \textsuperscript{...}
    text = _remove_command_with_braces(text, "textsuperscript")
    # Remove \footnote{...}
    text = _remove_command_with_braces(text, "footnote")
    # Remove \affiliation{...}
    text = _remove_command_with_braces(text, "affiliation")
    # Remove \email{...}
    text = _remove_command_with_braces(text, "email")

    # Remove \\ line breaks
    text = re.sub(r"\\\\", " ", text)

    # Clean remaining LaTeX formatting
    text = _clean_latex_text(text)

    return text if text else None


def _remove_command_with_braces(text: str, command: str) -> str:
    """Remove LaTeX command and its braced argument."""
    result = text
    pattern = re.compile(rf"\\{command}\s*\{{")

    while True:
        match = pattern.search(result)
        if not match:
            break

        brace_start = match.end() - 1
        content_end = _find_matching_brace(result, brace_start)
        if content_end is None:
            break

        # Remove the entire command including braces
        result = result[: match.start()] + result[content_end + 1 :]

    return result


def _find_matching_brace(text: str, start_pos: int) -> int | None:
    """Find position of closing brace matching opening brace at start_pos."""
    if start_pos >= len(text) or text[start_pos] != "{":
        return None

    depth = 0
    for i in range(start_pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return None


def _extract_abstract(tex_content: str) -> str | None:
    """Extract abstract from \\begin{abstract}...\\end{abstract} environment."""
    pattern = re.compile(
        r"\\begin\{abstract\}(.*?)\\end\{abstract\}",
        re.DOTALL,
    )
    match = pattern.search(tex_content)
    if not match:
        return None

    content = match.group(1)
    return _clean_latex_text(content)


def _clean_latex_text(text: str) -> str:
    """Clean LaTeX markup from text, preserving readable content."""
    result = text

    # Remove LaTeX comments (lines starting with %)
    result = re.sub(r"(?m)^\s*%.*$", "", result)
    # Remove inline comments (% not preceded by \)
    result = re.sub(r"(?<!\\)%.*$", "", result, flags=re.MULTILINE)

    # Handle common text formatting commands by extracting their content
    # \textbf{...}, \textit{...}, \emph{...}, etc.
    for cmd in ("textbf", "textit", "emph", "textrm", "textsf", "texttt", "textsc"):
        result = _unwrap_command(result, cmd)

    # Remove remaining simple commands without arguments
    result = re.sub(r"\\[a-zA-Z]+\s*(?![{[])", " ", result)

    # Clean up braces that were part of commands
    # But be careful not to remove math braces
    result = re.sub(r"(?<!\\)[{}]", "", result)

    # Normalize whitespace
    result = re.sub(r"\s+", " ", result)

    return result.strip()


def _unwrap_command(text: str, command: str) -> str:
    """Replace \\command{content} with just content."""
    result = text
    pattern = re.compile(rf"\\{command}\s*\{{")

    while True:
        match = pattern.search(result)
        if not match:
            break

        brace_start = match.end() - 1
        content = _extract_braced_content(result, brace_start)
        if content is None:
            break

        brace_end = _find_matching_brace(result, brace_start)
        if brace_end is None:
            break

        # Replace command with just its content
        result = result[: match.start()] + content + result[brace_end + 1 :]

    return result
