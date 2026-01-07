"""Format arXiv sections into summary, tree, and content outputs."""

from __future__ import annotations

from typing import Iterable

try:
    import tiktoken
except ImportError:  # pragma: no cover - optional dependency
    tiktoken = None

from arxiv2md.schemas import IngestionResult, SectionNode


def format_paper(
    *,
    arxiv_id: str,
    version: str | None,
    title: str | None,
    authors: list[str],
    abstract: str | None,
    sections: list[SectionNode],
    include_toc: bool,
) -> IngestionResult:
    """Create summary, section tree, and content."""
    tree = "Sections:\n" + _create_sections_tree(sections)
    content = _render_content(abstract=abstract, sections=sections, include_toc=include_toc)

    summary_lines = []
    if title:
        summary_lines.append(f"Title: {title}")
    summary_lines.append(f"ArXiv: {arxiv_id}")
    if version:
        summary_lines.append(f"Version: {version}")
    if authors:
        summary_lines.append(f"Authors: {', '.join(authors)}")
    summary_lines.append(f"Sections: {count_sections(sections)}")

    token_estimate = _format_token_count(tree + "\n" + content)
    if token_estimate:
        summary_lines.append(f"Estimated tokens: {token_estimate}")

    summary = "\n".join(summary_lines)

    return IngestionResult(summary=summary, sections_tree=tree, content=content)


def count_sections(sections: Iterable[SectionNode]) -> int:
    """Count total sections in the tree."""
    total = 0
    for section in sections:
        total += 1
        total += count_sections(section.children)
    return total


def _render_content(
    *,
    abstract: str | None,
    sections: list[SectionNode],
    include_toc: bool,
) -> str:
    blocks: list[str] = []
    if include_toc:
        toc = _render_toc(sections)
        if toc:
            blocks.append("## Contents\n" + toc)

    if abstract:
        blocks.append("## Abstract")
        blocks.append(abstract.strip())

    for section in sections:
        blocks.extend(_render_section(section))

    return "\n\n".join(block for block in blocks if block).strip()


def _render_section(section: SectionNode) -> list[str]:
    blocks: list[str] = []
    heading_prefix = "#" * min(section.level, 6)
    blocks.append(f"{heading_prefix} {section.title}")
    if section.markdown:
        blocks.append(section.markdown)
    for child in section.children:
        blocks.extend(_render_section(child))
    return blocks


def _render_toc(sections: list[SectionNode], indent: int = 0) -> str:
    lines: list[str] = []
    for section in sections:
        prefix = "  " * indent + "- "
        lines.append(prefix + section.title)
        if section.children:
            lines.append(_render_toc(section.children, indent + 1))
    return "\n".join(lines)


def _create_sections_tree(sections: list[SectionNode], indent: int = 0) -> str:
    lines: list[str] = []
    for section in sections:
        lines.append(" " * (indent * 4) + section.title)
        if section.children:
            lines.append(_create_sections_tree(section.children, indent + 1))
    return "\n".join(lines)


def _format_token_count(text: str) -> str | None:
    if not tiktoken:
        return None
    try:
        encoding = tiktoken.get_encoding("o200k_base")
        total_tokens = len(encoding.encode(text, disallowed_special=()))
    except Exception:
        return None

    if total_tokens >= 1_000_000:
        return f"{total_tokens / 1_000_000:.1f}M"
    if total_tokens >= 1_000:
        return f"{total_tokens / 1_000:.1f}k"
    return str(total_tokens)
