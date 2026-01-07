"""Inspect arXiv HTML structure to aid serialization."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import httpx
from bs4 import BeautifulSoup


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect arXiv HTML tags, classes, and attributes.")
    parser.add_argument("--url", help="URL to fetch (e.g. https://arxiv.org/html/2501.11120v1)")
    parser.add_argument("--file", help="Local HTML file path")
    parser.add_argument("--ltx-only", action="store_true", help="Show only classes starting with ltx_")
    args = parser.parse_args()

    if not args.url and not args.file:
        parser.error("Provide --url or --file")

    html = load_html(url=args.url, file_path=args.file)
    soup = BeautifulSoup(html, "html.parser")
    tags, classes, attrs = collect_stats(soup)

    print("Tags:")
    for name, count in tags.most_common():
        print(f"{name}: {count}")

    print("\nClasses:")
    for name, count in classes.most_common():
        if args.ltx_only and not name.startswith("ltx_"):
            continue
        print(f"{name}: {count}")

    print("\nAttributes:")
    for name, count in attrs.most_common():
        print(f"{name}: {count}")


def load_html(*, url: str | None, file_path: str | None) -> str:
    if url:
        response = httpx.get(url, follow_redirects=True, timeout=15.0)
        response.raise_for_status()
        return response.text

    path = Path(file_path or "")
    if not path.is_file():
        raise FileNotFoundError(f"HTML file not found: {path}")
    return path.read_text(encoding="utf-8")


def collect_stats(soup: BeautifulSoup) -> tuple[Counter, Counter, Counter]:
    tags = Counter()
    classes = Counter()
    attrs = Counter()

    for tag in soup.find_all(True):
        tags[tag.name] += 1
        for cls in tag.get("class", []):
            classes[cls] += 1
        for attr in tag.attrs:
            attrs[attr] += 1
    return tags, classes, attrs


if __name__ == "__main__":
    main()
