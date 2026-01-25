"""Shared HTML utilities for arXiv document processing."""

from __future__ import annotations

import re

try:
    from bs4 import BeautifulSoup
    from bs4.element import Tag
except ImportError as exc:  # pragma: no cover - runtime dependency check
    raise RuntimeError(
        "BeautifulSoup4 is required for HTML parsing (pip install beautifulsoup4)."
    ) from exc


def find_document_root(soup: BeautifulSoup) -> Tag:
    """Find the main document root element in an arXiv HTML document.

    Searches for the document root in the following order:
    1. <article class="ltx_document">
    2. Any <article> element
    3. <body> element
    4. The soup itself as fallback
    """
    root = soup.find("article", class_=re.compile(r"ltx_document"))
    if root:
        return root
    article = soup.find("article")
    if article:
        return article
    if soup.body:
        return soup.body
    return soup
