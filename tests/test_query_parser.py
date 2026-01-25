"""Tests for arXiv query parsing."""

from __future__ import annotations

import pytest

from arxiv2md.query_parser import parse_arxiv_input


@pytest.mark.parametrize(
    ("input_text", "arxiv_id", "version"),
    [
        ("2501.11120v1", "2501.11120v1", "v1"),
        ("https://arxiv.org/abs/2501.11120", "2501.11120", None),
        ("https://arxiv.org/pdf/2501.11120v2.pdf", "2501.11120v2", "v2"),
        ("cs/9901001v2", "cs/9901001v2", "v2"),
    ],
)
def test_parse_arxiv_inputs(
    input_text: str, arxiv_id: str, version: str | None
) -> None:
    query = parse_arxiv_input(input_text)

    assert query.arxiv_id == arxiv_id
    assert query.version == version
    assert query.html_url == f"https://arxiv.org/html/{arxiv_id}"
    assert query.ar5iv_url == f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}"
    assert query.latex_url == f"https://arxiv.org/e-print/{arxiv_id}"
    assert query.abs_url == f"https://arxiv.org/abs/{arxiv_id}"


def test_rejects_unknown_host() -> None:
    with pytest.raises(ValueError, match="Unsupported host"):
        parse_arxiv_input("https://example.com/abs/2501.11120")


def test_rejects_url_with_credentials_in_username() -> None:
    """Reject URLs with arxiv.org in the username (SSRF bypass attempt)."""
    with pytest.raises(ValueError, match="URLs with credentials are not allowed"):
        parse_arxiv_input("https://arxiv.org@evil.com/abs/2501.11120")


def test_rejects_url_with_full_credentials() -> None:
    """Reject URLs with username:password credentials."""
    with pytest.raises(ValueError, match="URLs with credentials are not allowed"):
        parse_arxiv_input("https://user:pass@arxiv.org/abs/2501.11120")


def test_rejects_subdomain_of_evil_host() -> None:
    """Reject URLs where arxiv.org is a subdomain of an attacker host."""
    with pytest.raises(ValueError, match="Unsupported host"):
        parse_arxiv_input("https://arxiv.org.evil.com/abs/2501.11120")


def test_accepts_www_arxiv_org() -> None:
    """Accept www.arxiv.org as a valid host."""
    query = parse_arxiv_input("https://www.arxiv.org/abs/2501.11120")
    assert query.arxiv_id == "2501.11120"
