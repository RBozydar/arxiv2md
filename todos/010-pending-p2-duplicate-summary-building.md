---
status: pending
priority: p2
issue_id: "010"
tags: [code-review, duplication, library]
dependencies: []
---

# Duplicate Summary Building Logic

## Problem Statement

Summary building logic is duplicated between `_ingest_from_latex()` in `ingestion.py` and `format_paper()` in `output_formatter.py`, violating DRY principles.

## Findings

**Location 1**: `/home/rbw/repo/arxiv2md/src/arxiv2md/ingestion.py` lines 193-202

```python
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
```

**Location 2**: `/home/rbw/repo/arxiv2md/src/arxiv2md/output_formatter.py` lines 44-61

```python
summary_lines = []
if title:
    summary_lines.append(f"Title: {title}")
summary_lines.append(f"ArXiv: {arxiv_id}")
if version:
    summary_lines.append(f"Version: {version}")
if authors:
    summary_lines.append(f"Authors: {', '.join(authors)}")
summary_lines.append(f"Sections: {count_sections(sections)}")
```

**Issue**: Same pattern, slightly different fields. If format changes, both must be updated.

## Proposed Solutions

### Option A: Have `_ingest_from_latex()` Call `format_paper()` (Recommended)
- **Pros**: Single source of truth, reuses existing function
- **Cons**: May need to handle LaTeX-specific formatting
- **Effort**: Medium
- **Risk**: Low

The `_ingest_from_latex()` function should construct the minimal data needed and call `format_paper()` like the HTML path does.

### Option B: Extract Shared Summary Builder
- **Pros**: Explicit shared function
- **Cons**: Another function to maintain
- **Effort**: Small
- **Risk**: Low

```python
def _build_summary(
    title: str | None,
    arxiv_id: str,
    version: str | None,
    authors: list[str],
    section_count: int | None = None,
    source: str | None = None,
) -> str:
    # Unified summary building
```

## Recommended Action

Option A - Refactor `_ingest_from_latex()` to use `format_paper()`.

## Technical Details

**Affected files**:
- `src/arxiv2md/ingestion.py`
- Possibly `src/arxiv2md/output_formatter.py`

## Acceptance Criteria

- [ ] Summary building logic exists in one place
- [ ] Both HTML and LaTeX paths produce consistent summaries
- [ ] Tests pass

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-26 | Issue identified in code review | Coherence reviewer flagged |
