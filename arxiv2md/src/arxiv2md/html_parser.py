"""Parse arXiv HTML into metadata and section structure."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from arxiv2md.schemas import SectionNode


try:
    from bs4 import BeautifulSoup
    from bs4.element import NavigableString, Tag
except ImportError as exc:  # pragma: no cover - runtime dependency check
    raise RuntimeError("BeautifulSoup4 is required for HTML parsing (pip install beautifulsoup4).") from exc


_HEADING_RE = re.compile(r"^h[1-6]$")


@dataclass
class ParsedArxivHtml:
    """Parsed content extracted from arXiv HTML."""

    title: str | None
    authors: list[str]
    abstract: str | None
    sections: list[SectionNode]


def parse_arxiv_html(html: str) -> ParsedArxivHtml:
    """Extract title, authors, abstract, and section tree from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    document_root = _find_document_root(soup)

    title = _extract_title(soup)
    authors = _extract_authors(soup)
    abstract = _extract_abstract(soup)
    sections = _extract_sections(document_root)

    return ParsedArxivHtml(title=title, authors=authors, abstract=abstract, sections=sections)


def _find_document_root(soup: BeautifulSoup) -> Tag:
    root = soup.find("article", class_=re.compile(r"ltx_document"))
    if root:
        return root
    article = soup.find("article")
    if article:
        return article
    if soup.body:
        return soup.body
    return soup


def _extract_title(soup: BeautifulSoup) -> str | None:
    title_tag = soup.find("h1", class_=re.compile(r"ltx_title"))
    if title_tag:
        return title_tag.get_text(" ", strip=True)
    if soup.title:
        return soup.title.get_text(" ", strip=True)
    return None


def _extract_authors(soup: BeautifulSoup) -> list[str]:
    authors_container = soup.find(class_=re.compile(r"ltx_authors"))
    if not authors_container:
        return []
    author_nodes = authors_container.find_all(
        lambda tag: tag.name == "span"
        and "ltx_text" in tag.get("class", [])
        and "ltx_font_bold" in tag.get("class", [])
    )
    if not author_nodes:
        author_nodes = authors_container.find_all(class_=re.compile(r"ltx_author|ltx_personname"))

    authors: list[str] = []
    for node in author_nodes:
        text = _clean_author_text(node)
        if text and text not in authors:
            authors.append(text)
    return authors


def _clean_author_text(node: Tag) -> str:
    clone = BeautifulSoup(str(node), "html.parser")
    for sup in clone.find_all("sup"):
        sup.decompose()
    text = clone.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def _extract_abstract(soup: BeautifulSoup) -> str | None:
    abstract = soup.find(class_=re.compile(r"ltx_abstract"))
    if not abstract:
        return None
    return abstract.get_text(" ", strip=True)


def _extract_sections(root: Tag) -> list[SectionNode]:
    headings = [heading for heading in _iter_headings(root) if not _is_title_heading(heading)]
    sections: list[SectionNode] = []
    stack: list[SectionNode] = []

    for heading in headings:
        level = int(heading.name[1])
        title = heading.get_text(" ", strip=True)
        anchor = heading.get("id") or heading.parent.get("id")
        html = _collect_section_html(heading)

        node = SectionNode(title=title, level=level, anchor=anchor, html=html)

        while stack and stack[-1].level >= level:
            stack.pop()

        if stack:
            stack[-1].children.append(node)
        else:
            sections.append(node)

        stack.append(node)

    return sections


def _iter_headings(root: Tag) -> Iterable[Tag]:
    for heading in root.find_all(_HEADING_RE):
        if heading.find_parent("nav"):
            continue
        if heading.find_parent(class_=re.compile(r"ltx_abstract")):
            continue
        yield heading


def _is_title_heading(heading: Tag) -> bool:
    classes = heading.get("class", [])
    return "ltx_title_document" in classes


def _collect_section_html(heading: Tag) -> str | None:
    section = heading.find_parent("section")
    if not section:
        return None

    parts: list[str] = []
    started = False
    for child in section.children:
        if child == heading:
            started = True
            continue
        if not started:
            continue
        if isinstance(child, Tag) and child.name == "section":
            continue
        if isinstance(child, Tag) and any(
            cls.startswith("ltx_section") or cls.startswith("ltx_subsection") or cls.startswith("ltx_subsubsection")
            for cls in child.get("class", [])
        ):
            continue
        if isinstance(child, NavigableString):
            text = str(child)
            if text.strip():
                parts.append(text)
            continue
        if isinstance(child, Tag):
            parts.append(str(child))
    html = "".join(parts).strip()
    return html or None
