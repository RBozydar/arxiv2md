"""Ingestion pipeline for arXiv HTML -> Markdown."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Literal

from arxiv2md.exceptions import HTMLNotAvailableError
from arxiv2md.fetch import fetch_arxiv_html
from arxiv2md.html_parser import parse_arxiv_html
from arxiv2md.latex_fetch import fetch_arxiv_source
from arxiv2md.latex_parser import (
    convert_latex_to_markdown,
    detect_main_tex,
    extract_latex_metadata,
)
from arxiv2md.markdown import convert_fragment_to_markdown
from arxiv2md.output_formatter import format_paper
from arxiv2md.schemas import IngestionResult
from arxiv2md.sections import filter_sections

_REFERENCE_TITLES = ("references", "bibliography")
_ABSTRACT_TITLE = "abstract"


@dataclass
class IngestionOptions:
    """Options for paper ingestion.

    Attributes:
        remove_refs: If True, remove references/bibliography sections.
        remove_toc: If True, exclude table of contents from output.
        remove_inline_citations: If True, completely remove inline citation
            links from the output.
        section_filter_mode: Mode for section filtering ("include" or "exclude").
        sections: List of section names to include or exclude.
        force_latex: If True, skip HTML fetching and use LaTeX source directly.
        disable_latex_fallback: If True, do not fall back to LaTeX on HTML failure.
    """

    remove_refs: bool = False
    remove_toc: bool = False
    remove_inline_citations: bool = False
    section_filter_mode: Literal["include", "exclude"] = "exclude"
    sections: list[str] = field(default_factory=list)
    force_latex: bool = False
    disable_latex_fallback: bool = False


async def ingest_paper(
    *,
    arxiv_id: str,
    version: str | None,
    html_url: str,
    ar5iv_url: str | None = None,
    options: IngestionOptions | None = None,
) -> tuple[IngestionResult, dict[str, str | list[str] | None]]:
    """Fetch, parse, and serialize an arXiv paper into Markdown.

    Attempts to fetch HTML from arxiv.org, then ar5iv as fallback.
    If neither HTML source is available, falls back to fetching LaTeX
    source and converting via pandoc.

    Args:
        arxiv_id: The arXiv paper identifier.
        version: Optional version string (e.g., "v1").
        html_url: Primary HTML URL (arxiv.org).
        ar5iv_url: Fallback ar5iv HTML URL.
        options: Processing options for ingestion. Uses defaults if None.

    Returns:
        Tuple of (result, metadata) where metadata includes source type.

    Raises:
        RuntimeError: If fetching fails and fallback is disabled or unavailable.
    """
    opts = options or IngestionOptions()
    source = "html"

    # Force LaTeX mode: skip HTML entirely
    if opts.force_latex:
        source = "latex"
        result, metadata = await _ingest_from_latex(
            arxiv_id=arxiv_id,
            version=version,
            remove_toc=opts.remove_toc,
        )
        metadata["source"] = source
        return result, metadata

    try:
        html = await fetch_arxiv_html(
            html_url,
            arxiv_id=arxiv_id,
            version=version,
            use_cache=True,
            ar5iv_url=ar5iv_url,
        )
        parsed = parse_arxiv_html(html)
    except HTMLNotAvailableError:
        # If LaTeX fallback is disabled, re-raise the error
        if opts.disable_latex_fallback:
            raise

        # Fallback to LaTeX source conversion
        source = "latex"
        result, metadata = await _ingest_from_latex(
            arxiv_id=arxiv_id,
            version=version,
            remove_toc=opts.remove_toc,
        )
        metadata["source"] = source
        return result, metadata

    filtered_sections = filter_sections(
        parsed.sections, mode=opts.section_filter_mode, selected=opts.sections
    )
    if opts.remove_refs:
        filtered_sections = filter_sections(
            filtered_sections, mode="exclude", selected=_REFERENCE_TITLES
        )

    # Check if abstract should be included based on section filter
    selected_lower = [s.lower() for s in opts.sections]
    if opts.section_filter_mode == "exclude":
        include_abstract = _ABSTRACT_TITLE not in selected_lower
    else:  # include mode
        include_abstract = not opts.sections or _ABSTRACT_TITLE in selected_lower

    for section in filtered_sections:
        _populate_section_markdown(
            section, remove_inline_citations=opts.remove_inline_citations
        )

    result = format_paper(
        arxiv_id=arxiv_id,
        version=version,
        title=parsed.title,
        authors=parsed.authors,
        abstract=parsed.abstract if include_abstract else None,
        sections=filtered_sections,
        include_toc=not opts.remove_toc,
        include_abstract_in_tree=parsed.abstract is not None,
        source=source,
    )

    metadata = {
        "title": parsed.title,
        "authors": parsed.authors,
        "abstract": parsed.abstract,
        "source": source,
    }

    return result, metadata


async def _ingest_from_latex(
    *,
    arxiv_id: str,
    version: str | None,
    remove_toc: bool,
) -> tuple[IngestionResult, dict[str, str | list[str] | None]]:
    """Ingest paper from LaTeX source via pandoc conversion.

    Args:
        arxiv_id: The arXiv paper identifier.
        version: Optional version string.
        remove_toc: If True, exclude table of contents from output.

    Returns:
        Tuple of (IngestionResult, metadata dict).

    Raises:
        RuntimeError: If source bundle cannot be fetched or converted.
        ValueError: If no .tex files found in source bundle.
    """
    source_dir = await fetch_arxiv_source(arxiv_id, version)
    main_tex = detect_main_tex(source_dir)

    # Convert LaTeX to Markdown via pandoc (blocking call wrapped in thread)
    markdown_content = await asyncio.to_thread(convert_latex_to_markdown, main_tex)

    # Extract metadata from LaTeX source
    tex_content = main_tex.read_text(errors="replace")
    latex_metadata = extract_latex_metadata(tex_content)

    title = latex_metadata.get("title")
    authors = latex_metadata.get("authors") or []
    abstract = latex_metadata.get("abstract")

    # Build summary lines
    summary_lines = []
    if title:
        summary_lines.append(f"Title: {title}")
    summary_lines.append(f"ArXiv: {arxiv_id}")
    if version:
        summary_lines.append(f"Version: {version}")
    if authors:
        summary_lines.append(f"Authors: {', '.join(authors)}")
    summary_lines.append("Source: LaTeX (via Pandoc)")
    summary = "\n".join(summary_lines)

    # Build minimal sections tree
    sections_tree = "Sections:\n(Converted from LaTeX source)"

    # Build content with optional ToC placeholder and abstract
    content_blocks: list[str] = []
    if not remove_toc:
        content_blocks.append(
            "## Contents\n(Table of contents not available for LaTeX source)"
        )

    if abstract:
        content_blocks.append("## Abstract")
        content_blocks.append(abstract.strip())

    # Add the pandoc-converted markdown content
    content_blocks.append(markdown_content)

    content = "\n\n".join(block for block in content_blocks if block).strip()

    result = IngestionResult(
        summary=summary,
        sections_tree=sections_tree,
        content=content,
    )

    metadata: dict[str, str | list[str] | None] = {
        "title": title,
        "authors": authors,
        "abstract": abstract,
    }

    return result, metadata


def _populate_section_markdown(
    section, *, remove_inline_citations: bool = False
) -> None:
    if section.html:
        section.markdown = convert_fragment_to_markdown(
            section.html, remove_inline_citations=remove_inline_citations
        )
    for child in section.children:
        _populate_section_markdown(
            child, remove_inline_citations=remove_inline_citations
        )
