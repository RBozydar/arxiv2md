# arxiv2md Implementation Plan

## 1) High-level architecture
- Forked copy with selective edits:
  - Start from `gitingest/` server + static assets and modify in-place for arXiv.
  - This is not a shared dependency; we accept drift in exchange for faster iteration.
- Reuse from `gitingest/` (copied, then edited):
  - FastAPI app scaffold: `src/server/main.py`, `src/server/server_config.py`
  - API response/error handling: `src/server/routers_utils.py`, `src/server/models.py` (structure reused, fields adapted)
  - Templates base/layout, shared components, static assets: `src/server/templates/base.jinja`, `src/server/templates/components/*.jinja`, `src/static/*`
  - Result rendering behavior (summary + tree + content): `src/server/templates/components/result.jinja` with label changes
  - Logging config: `src/arxiv2md/utils/logging_config.py` (copied from gitingest)
- Remove for v1 (hosted service utilities):
  - S3 support, metrics server, Sentry, and rate limiting.
  - Any gitingest production-specific settings (trusted hosts, etc.) that are not needed for localhost.
- Adapt/replace for arXiv:
  - Query parsing: replace repo URL/slug parsing with arXiv ID/URL normalization
  - Ingestion pipeline: replace Git clone + filesystem traversal with HTML fetch + parse + section tree build
  - Output formatting: replace file tree and file content assembly with section tree + section content assembly
  - Request/response schema fields: replace git-specific fields (`repo_url`, `short_repo_url`) with paper-specific (`arxiv_id`, `title`, `version`)
  - UI form controls: replace pattern include/exclude with section filtering controls
- New modules required:
  - `arxiv2md/config.py`: local-only configuration (cache path, timeouts, limits)
  - `arxiv2md/query_parser.py`: normalize arXiv URLs/IDs and select canonical HTML endpoints
  - `arxiv2md/fetch.py`: HTML retrieval with retries, timeouts, and caching
  - `arxiv2md/html_parser.py`: extract title, authors, abstract, headings, section hierarchy
  - `arxiv2md/markdown.py`: custom arXiv serializer using the HTML structure
  - `arxiv2md/sections.py`: section tree model + filtering logic
  - `arxiv2md/output_formatter.py`: summary + section tree + content assembly + token counting

## 2) Module-by-module mapping
```
gitingest/query_parser.py          -> arxiv2md/query_parser.py
gitingest/clone.py                 -> (removed; no clone step)
gitingest/ingestion.py             -> arxiv2md/ingestion.py
gitingest/output_formatter.py      -> arxiv2md/output_formatter.py
gitingest/schemas/*                -> arxiv2md/schemas/*
gitingest/utils/ingestion_utils.py -> arxiv2md/utils/section_filter_utils.py
gitingest/config.py                -> arxiv2md/config.py
server/query_processor.py          -> server/query_processor.py (adapted to arxiv)
server/models.py                   -> server/models.py (field changes)
server/routers/ingest.py           -> server/routers/ingest.py (labels + docs + args)
server/templates/git.jinja         -> server/templates/arxiv.jinja (or reuse with content swap)
server/templates/components/git_form.jinja
                                  -> server/templates/components/arxiv_form.jinja
static/js/git.js                   -> static/js/arxiv.js
static/js/git_form.js              -> static/js/arxiv_form.js
```
Mapping details:
- `gitingest.query_parser.parse_remote_repo` -> `arxiv2md.query_parser.parse_arxiv_input`
  - Inputs: arXiv ID, `arxiv.org/abs/...`, `arxiv.org/pdf/...`, `arxiv.org/html/...`
  - Outputs: normalized ID, version, canonical HTML URL, and display URL
- `gitingest.ingestion.ingest_query` -> `arxiv2md.ingestion.ingest_paper`
  - Inputs: arXiv query + selected sections
  - Outputs: section tree + section markdown + summary
- `gitingest.output_formatter.format_node` -> `arxiv2md.output_formatter.format_sections`
  - Outputs: summary (paper metadata + token estimate), section tree, content

## 3) ArXiv ingestion pipeline
ASCII flow:
```
User input -> normalize ID/URL -> fetch HTML -> parse DOM -> convert to Markdown
          -> build section tree -> apply section filter -> format summary/tree/content
          -> cache + respond
```
- URL normalization
  - Accept inputs: raw IDs (`2401.12345`), versioned IDs (`2401.12345v2`), and URLs for `abs`, `pdf`, or `html`.
  - Normalize to `{id}{v?}` and canonical HTML URL: `https://arxiv.org/html/{id}{v?}`.
  - Store display URL for UI and metadata (e.g., `https://arxiv.org/abs/{id}{v?}`).
- HTML fetch strategy
  - Use `httpx` or `requests` with:
    - Short timeout (e.g., 10s) and limited retries for 5xx/429.
    - User-Agent set to identify the service.
  - Handle `text/html` validation; reject non-HTML responses.
- Error handling when HTML is unavailable
  - If `404` or non-HTML: return a structured error stating that HTML is unavailable and PDF OCR is not supported in v1.
  - If `429/5xx`: surface transient error and suggest retry.
- Caching strategy
  - Local-only cache under `ARXIV2MD_CACHE_PATH` (or default in `arxiv2md/config.py`) keyed by `{arxiv_id}:{version}`.
  - Cache eviction policy: LRU or time-based cleanup job (defer to v1.1 if needed).

## 4) Markdown conversion strategy
- Use the static arXiv HTML endpoint (`/html/{id}`), no Playwright or browser rendering.
- Implement a custom serializer over the regimented `ltx_*` DOM:
  - Headings (`h1`-`h6`) -> Markdown headings with numbering preserved.
  - Paragraphs (`div.ltx_para`, `p.ltx_p`) -> inline text with math and citations.
  - MathML -> inline LaTeX from `annotation[encoding="application/x-tex"]`.
  - Tables (`ltx_tabular`) -> Markdown tables; equation tables -> `$$ ... $$`.
  - Figures -> caption text + image source (if present).
  - TOC and references -> optional include/exclude flags.
- Port the essential cleanup logic from `contentScript.js` (math, tables, refs/TOC).
- Use a generic HTML->MD fallback only for unknown nodes (if needed).
- Add a helper script to inspect tag/class usage from the HTML endpoint (`scripts/inspect_arxiv_html.py`).

## 5) Section detection & filtering
- Section detection
  - Extract headings (`h1`-`h6`) and LaTeXML section markers (e.g., elements with classes like `ltx_section`).
  - Build a hierarchical section tree based on heading levels.
  - Special-case common headings: `Abstract`, `References`, `Appendix`, `Acknowledgments`.
  - Attach content ranges to each section (text between heading boundaries).
- Filtering model
  - Sections replace file/dir selection.
  - Provide include/exclude modes similar to gitingest patterns:
    - Include only selected sections (default: include all).
    - Exclude selected sections (e.g., References, Appendix).
- UI mapping to gitingest selector
  - The left panel becomes a section list/tree.
  - Each section has a checkbox; parent checkbox toggles children.
  - Section list is derived from parsed headings; if none, show a single “Body” section.
  - The “directory structure” panel becomes a “Sections” panel with tree formatting.

## 6) Web UI changes
- Reuse
  - `src/server/templates/base.jinja` and `components/result.jinja` (rename labels only).
  - Existing CSS/JS scaffolding in `src/static/`.
- Changes
  - Replace `git_form.jinja` with `arxiv_form.jinja`:
    - Input placeholder: “https://arxiv.org/abs/... or 2401.12345”
    - Remove PAT controls; add toggles for:
      - Remove references
      - Remove table of contents
      - Section include/exclude mode
  - Replace text labels:
    - “Directory Structure” -> “Sections”
    - “Files Content” -> “Paper Content”
  - JS updates:
    - `static/js/arxiv.js` to auto-submit on URL param if present (parallel to `git.js`)
    - `static/js/arxiv_form.js` to manage section toggles and preview tree
- Result rendering
  - Summary includes title, arXiv ID, version, token estimate, section count.
  - Tree shows section headings with depth indentation.

## 7) CLI parity (planned)
- Provide a CLI entry similar to `gitingest.__main__`:
  - Example: `arxiv2md 2401.12345v2 --remove-refs --remove-toc --sections "Abstract,Introduction"`
  - Output to file or stdout (`-o -`) with summary + markdown.
  - Keep CLI behavior consistent with gitingest (errors via non-zero exit).

## 8) Explicit non-goals for v1
- PDF extraction or OCR (no PDF parsing fallback).
- Citation resolution against external databases (Crossref, Semantic Scholar).
- Advanced math rendering beyond annotation extraction.
- Multi-paper batch ingest or dataset crawling.
- Section semantic classification beyond headings (e.g., “Methods” inferred from text).
- Persistent user accounts or saved history.
