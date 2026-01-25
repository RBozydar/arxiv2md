---
title: "feat: Add LaTeX to Markdown via Pandoc fallback"
type: feat
date: 2026-01-25
task_list_id: 83f7c72e-f0e0-442f-9068-5a6eac19696b
---

# feat: Add LaTeX to Markdown via Pandoc fallback

## Overview

When an arXiv paper doesn't have an HTML version available (common for older papers), automatically fall back to fetching the LaTeX source bundle and converting it to Markdown via pandoc. This ensures arxiv2md can process any arXiv paper, not just those with HTML versions.

## Problem Statement

Currently, arxiv2md fails with an error when a paper doesn't have an HTML version:

```
This paper does not have an HTML version available on arXiv.
arxiv2md requires papers to be available in HTML format.
Older papers may only be available as PDF.
```

Many papers (especially pre-2023) only exist as PDF/LaTeX on arXiv. Users wanting to include these papers in LLM context windows have no automated option.

## Proposed Solution

Add a transparent fallback chain: **HTML → ar5iv → LaTeX**

When both HTML sources fail with 404, fetch the LaTeX source bundle from arXiv, extract the main `.tex` file, and convert to Markdown using pandoc (via `pypandoc_binary`).

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     ingest_paper()                          │
├─────────────────────────────────────────────────────────────┤
│  1. Try HTML (arxiv.org/html/{id})                          │
│     └─ Success → parse_arxiv_html() → format_paper()        │
│                                                             │
│  2. Try ar5iv (ar5iv.labs.arxiv.org/html/{id})              │
│     └─ Success → parse_arxiv_html() → format_paper()        │
│                                                             │
│  3. Try LaTeX (arxiv.org/e-print/{id})                      │
│     ├─ fetch_arxiv_source() → extract .tar.gz               │
│     ├─ detect_main_tex() → find \documentclass              │
│     ├─ pypandoc.convert_file() → Markdown                   │
│     └─ extract_latex_metadata() → title, authors, abstract  │
│                                                             │
│  4. All failed → RuntimeError with helpful message          │
└─────────────────────────────────────────────────────────────┘
```

### New Modules

```
src/arxiv2md/
├── fetch.py           # Existing - unchanged
├── latex_fetch.py     # NEW: fetch & extract source bundles
├── latex_parser.py    # NEW: main file detection, pandoc conversion, metadata
├── ingestion.py       # MODIFIED: add fallback logic
├── query_parser.py    # MODIFIED: add latex_url
└── schemas/
    └── query.py       # MODIFIED: add latex_url field
```

## Technical Approach

### 1. Dependency: pypandoc_binary

Add to `pyproject.toml`:

```toml
dependencies = [
    # ... existing deps
    "pypandoc_binary>=1.11",  # Bundles pandoc binary (~80MB)
]
```

**Why pypandoc_binary over alternatives:**
- Zero install friction - no system pandoc required
- Works across platforms (Linux, macOS, Windows)
- Target audience (LLM users) values "just works" over package size

### 2. Source Bundle Fetching (`latex_fetch.py`)

```python
async def fetch_arxiv_source(
    arxiv_id: str,
    version: str | None,
    *,
    use_cache: bool = True,
) -> Path:
    """Fetch and extract arXiv source bundle to temp directory.

    Returns path to extracted directory containing .tex files.
    """
```

**Source acquisition strategy:**
1. Primary: `https://arxiv.org/e-print/{id}` (direct download)
2. Fallback: `https://export.arxiv.org/api/query?id_list={id}` (API with redirect)

**Archive handling:**
- Most submissions: `.tar.gz` containing multiple files
- Some submissions: `.gz` single file (just the main .tex)
- Use `tarfile` and `gzip` from stdlib

### 3. Main File Detection (`latex_parser.py`)

Based on [arXiv's AutoTeX behavior](https://info.arxiv.org/help/submit_tex.html):

```python
def detect_main_tex(source_dir: Path) -> Path:
    """Find the main .tex file in an arXiv source bundle.

    Detection order:
    1. File containing \\documentclass directive
    2. File named 'ms.tex' (arXiv convention)
    3. Alphabetically first .tex file

    Raises ValueError if no .tex files found.
    """
```

**Multi-file handling:** Pandoc automatically resolves `\input{}` and `\include{}` directives when given the main file path and all sources are in the same directory. No manual stitching required.

### 4. LaTeX to Markdown Conversion

```python
def convert_latex_to_markdown(main_tex: Path) -> str:
    """Convert LaTeX file to Markdown using pandoc."""
    return pypandoc.convert_file(
        str(main_tex),
        'markdown',
        format='latex',
        extra_args=['--wrap=none']  # Don't wrap lines
    )
```

**Quality considerations for LLM consumption:**
- Math stays as LaTeX (`$...$`) - LLMs handle this natively
- Figures become `![alt](path)` - fine since LLMs can't see images anyway
- Tables may degrade but imperfect tables > no content
- Author comments (`%`) are stripped - reduces noise

### 5. Metadata Extraction from LaTeX

```python
def extract_latex_metadata(tex_content: str) -> dict:
    """Extract title, authors, abstract from LaTeX preamble."""
```

Parse LaTeX commands:
- `\title{...}` → title
- `\author{...}` → authors (may need splitting on `\and`)
- `\begin{abstract}...\end{abstract}` → abstract

### 6. Fallback Integration in `ingestion.py`

```diff
async def ingest_paper(...) -> tuple[IngestionResult, dict]:
    """Fetch, parse, and serialize an arXiv paper into Markdown."""
+   source = "html"

    try:
        html = await fetch_arxiv_html(html_url, arxiv_id=arxiv_id, ...)
        parsed = parse_arxiv_html(html)
    except RuntimeError as e:
        if "does not have an HTML version" not in str(e):
            raise
+       # Fallback to LaTeX
+       source = "latex"
+       source_dir = await fetch_arxiv_source(arxiv_id, version)
+       main_tex = detect_main_tex(source_dir)
+       markdown = convert_latex_to_markdown(main_tex)
+       metadata = extract_latex_metadata(main_tex.read_text())
+       # Build IngestionResult from LaTeX output
+       ...

    # ... rest of processing
+   # Include source indicator in result
```

### 7. CLI Enhancements

Add flags to `__main__.py`:

```python
parser.add_argument(
    "--latex",
    action="store_true",
    help="Force LaTeX source processing (skip HTML even if available).",
)
parser.add_argument(
    "--no-latex-fallback",
    action="store_true",
    help="Disable LaTeX fallback (fail if HTML unavailable).",
)
```

### 8. Source Provenance in Output

Include source indicator in summary:

```markdown
# Paper Title
> Authors: Alice, Bob
> arXiv: 2401.12345v1
> Source: LaTeX (via Pandoc)
> Tokens: ~12.5K
```

## Acceptance Criteria

### Functional Requirements

- [ ] Papers without HTML versions are successfully converted via LaTeX fallback
- [ ] Multi-file LaTeX projects are handled correctly (main file auto-detected)
- [ ] Metadata (title, authors, abstract) is extracted from LaTeX preamble
- [ ] Math expressions render as LaTeX in output (`$...$`)
- [ ] `--latex` flag forces LaTeX mode even when HTML exists
- [ ] `--no-latex-fallback` flag disables fallback behavior
- [ ] Source provenance is included in output summary

### Non-Functional Requirements

- [ ] Fallback adds <2s latency for typical papers
- [ ] Error messages clearly explain what failed and why
- [ ] Cache works for LaTeX sources (same TTL as HTML)

### Quality Gates

- [ ] Tests cover main file detection with various arXiv bundle structures
- [ ] Tests verify pandoc conversion produces valid Markdown
- [ ] Integration test confirms full fallback chain works

## Code Changes (Unified Diff Format)

### pyproject.toml

```diff
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -8,6 +8,7 @@ dependencies = [
     "loguru>=0.7.0",
     "pydantic>=2.0.0",
     "python-dotenv>=1.0.0",
     "tiktoken>=0.7.0",
+    "pypandoc_binary>=1.11",
 ]
```

### src/arxiv2md/schemas/query.py

```diff
--- a/src/arxiv2md/schemas/query.py
+++ b/src/arxiv2md/schemas/query.py
@@ -15,6 +15,7 @@ class ArxivQuery(BaseModel):
     html_url: str
     ar5iv_url: str
+    latex_url: str
     abs_url: str
```

### src/arxiv2md/query_parser.py

```diff
--- a/src/arxiv2md/query_parser.py
+++ b/src/arxiv2md/query_parser.py
@@ -26,6 +26,7 @@ def parse_arxiv_input(input_text: str) -> ArxivQuery:
     normalized_id, version = _extract_arxiv_id(raw)
     html_url = f"https://{_ARXIV_HOST}/html/{normalized_id}"
     ar5iv_url = f"https://ar5iv.labs.arxiv.org/html/{normalized_id}"
+    latex_url = f"https://{_ARXIV_HOST}/e-print/{normalized_id}"
     abs_url = f"https://{_ARXIV_HOST}/abs/{normalized_id}"
```

## Tasks

Run `/workflows:work` with this plan to execute. Tasks are stored in `~/.claude/tasks/83f7c72e-f0e0-442f-9068-5a6eac19696b/`.

To work on these tasks from another session:
```
skill: import-tasks 83f7c72e-f0e0-442f-9068-5a6eac19696b
```

**Task dependency graph:**

```
#1 Add pypandoc_binary dependency
 ├─► #2 Create latex_fetch.py ─────┐
 └─► #3 Create latex_parser.py ────┼─► #5 Extend ingestion.py ─┬─► #6 Add --latex CLI flag
                                   │                          ├─► #7 Add source provenance
#4 Add latex_url to schema ────────┘                          └─► #8 Add tests
```

## References

### Internal References

- Existing fallback pattern: `src/arxiv2md/fetch.py:42-59`
- Configuration pattern: `src/arxiv2md/config.py`
- Query schema: `src/arxiv2md/schemas/query.py`
- Error handling: `src/server/query_processor.py:25-35`

### External References

- [arXiv AutoTeX main file detection](https://info.arxiv.org/help/submit_tex.html)
- [pypandoc documentation](https://pypi.org/project/pypandoc/)
- [pypandoc_binary package](https://pypi.org/project/pypandoc-binary/)
- [Pandoc LaTeX reader options](https://pandoc.org/MANUAL.html#reader-options)

### Research Sources

- [uv package manager docs](https://docs.astral.sh/uv/guides/install-python/)
- [pypandoc PyPI](https://pypi.org/project/pypandoc/)
- [arXiv submission guidelines](https://info.arxiv.org/help/submit/index.html)
