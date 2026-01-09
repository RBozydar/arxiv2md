# AGENTS.md

Quick context for future sessions working in this repo.

## Project goal
Build `arxiv2md`, a local-first web app + CLI that mirrors gitingest UX but ingests arXiv HTML and outputs Markdown for LLM context windows.

## Current state (what was built)
- Forked `gitingest` server/static into `arxiv2md/` with selective edits for arXiv.
- Implemented arXiv pipeline:
  - `arxiv2md/src/arxiv2md/query_parser.py`: parse IDs/URLs -> canonical HTML URL.
  - `arxiv2md/src/arxiv2md/fetch.py`: httpx fetch + local cache (TTL).
  - `arxiv2md/src/arxiv2md/html_parser.py`: title/authors/abstract + section tree from LaTeXML HTML.
  - `arxiv2md/src/arxiv2md/markdown.py`: custom HTML->Markdown serializer (math/table handling).
  - `arxiv2md/src/arxiv2md/sections.py`: include/exclude filtering.
  - `arxiv2md/src/arxiv2md/output_formatter.py`: summary/tree/content + token estimate.
  - `arxiv2md/src/arxiv2md/ingestion.py`: orchestrates fetch -> parse -> filter -> serialize.
- API wiring updated: `arxiv2md/src/server/query_processor.py`, `arxiv2md/src/server/routers/ingest.py`, `arxiv2md/src/server/routers_utils.py`.
- UI updated: `arxiv2md/src/server/templates/components/arxiv_form.jinja` with section filter + remove refs/TOC toggles.
- CLI added: `arxiv2md/src/arxiv2md/__main__.py` with `--remove-refs`, `--remove-toc`, `--section-filter-mode`, `--sections`, `--section`, `-o`, and optional `--include-tree`.
- Packaging added: root `pyproject.toml` with `arxiv2md` script entry.
- Tests added: `arxiv2md/tests/test_query_parser.py`, `arxiv2md/tests/test_html_parser.py`, `arxiv2md/tests/test_markdown.py`.
- Docs added: root `README.md` with local web/CLI setup.

## Repo layout (important dirs)
- `arxiv2md/`: arXiv app (server + package + static).
  - `arxiv2md/src/arxiv2md/`: core pipeline modules.
  - `arxiv2md/src/server/`: FastAPI app + templates.
  - `arxiv2md/src/static/`: JS/CSS assets.
- `gitingest/`: original upstream; used only as reference.
- `arxiv-markdown-parser-plugin/`: Chrome extension reference for HTML logic.
- `scripts/inspect_arxiv_html.py`: helper to inspect HTML tag/class usage.

## How to run (local)
Web app:
1) `python -m venv .venv`
2) `.\.venv\Scripts\activate`
3) `pip install -e .[server]`
4) `uvicorn server.main:app --reload --app-dir arxiv2md/src`

CLI:
1) `pip install -e .`
2) `arxiv2md https://arxiv.org/html/2501.11120v1 -o -`

## Known quirks
- CLI defaults to summary + content only (no section tree). Use `--include-tree` if needed.
- Section tree still includes very deep headings from arXiv HTML; UI allows filtering via section titles.

## Suggested next steps
- Update result labels in UI ("Sections" vs "Contents") and fine-tune section selection UX.
- Add integration test for `/api/ingest` with mocked fetch.
- Consider a root-level shim for `python -m arxiv2md` without install (optional).
