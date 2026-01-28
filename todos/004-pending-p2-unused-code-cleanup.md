---
status: pending
priority: p2
issue_id: "004"
tags: [code-review, cleanup, library]
dependencies: []
---

# Unused Code Cleanup

## Problem Statement

Multiple pieces of code are defined but never used, adding maintenance burden and confusion.

## Findings

### 1. `RateLimitError` Exception (Never Raised)

**Location**: `/home/rbw/repo/arxiv2md/src/arxiv2md/exceptions.py` lines 20-21

```python
class RateLimitError(FetchError):
    """Rate limited by arXiv."""
```

Exported in `__init__.py` but never raised anywhere. HTTP 429 is handled via retry logic in `http_utils.py`.

### 2. Unused `ArxivQuery` Fields

**Location**: `/home/rbw/repo/arxiv2md/src/arxiv2md/schemas/query.py` lines 34-37

```python
latex_url: str      # Generated but never used
abs_url: str        # Generated but never used
id: UUID            # Generated but never used
cache_dir: Path     # Generated but never used
```

- `latex_url`: `latex_fetch.py` constructs its own URL
- `abs_url`: Never accessed
- `id`: UUID generated but never used
- `cache_dir`: Uses `cache_dir_for()` function instead

### 3. Unused Logging Infrastructure

**Location**: `/home/rbw/repo/arxiv2md/src/arxiv2md/utils/logging_config.py` (201 lines)

Elaborate logging configuration with Kubernetes detection, JSON sinks, and loguru integration. Never imported by library/CLI code.

### 4. Unused `SectionNode.anchor` Field

**Location**: `/home/rbw/repo/arxiv2md/src/arxiv2md/schemas/sections.py` line 13

Extracted from HTML but never used in output formatting.

### 5. Dead Type-Narrowing Code

**Locations**:
- `/home/rbw/repo/arxiv2md/src/arxiv2md/fetch.py` lines 107-108
- `/home/rbw/repo/arxiv2md/src/arxiv2md/latex_fetch.py` lines 94-95

```python
if isinstance(result, bytes):
    return result.decode("utf-8")
```

These `isinstance` checks are for cases that cannot happen given `return_bytes=False`.

## Proposed Solutions

### Option A: Remove All Unused Code (Recommended)
- **Pros**: Cleaner codebase, reduced maintenance burden
- **Cons**: Some may be intended for future use
- **Effort**: Small
- **Risk**: Low (can be re-added if needed)

**Items to remove**:
1. Delete `RateLimitError` from `exceptions.py` and `__init__.py`
2. Remove unused `ArxivQuery` fields and their generation in `query_parser.py`
3. Delete `utils/` directory entirely (move to server if needed there)
4. Remove `anchor` field from `SectionNode` and extraction in `html_parser.py`
5. Remove impossible type-narrowing branches

### Option B: Keep But Document as Future Use
- **Pros**: No effort
- **Cons**: Accumulates dead code
- **Effort**: None
- **Risk**: Technical debt

## Recommended Action

Option A - Remove unused code.

## Technical Details

**Estimated LOC reduction**: ~270 lines

**Files affected**:
- `src/arxiv2md/exceptions.py`
- `src/arxiv2md/__init__.py`
- `src/arxiv2md/schemas/query.py`
- `src/arxiv2md/query_parser.py`
- `src/arxiv2md/schemas/sections.py`
- `src/arxiv2md/html_parser.py`
- `src/arxiv2md/fetch.py`
- `src/arxiv2md/latex_fetch.py`
- `src/arxiv2md/utils/` (delete directory)

## Acceptance Criteria

- [ ] `RateLimitError` removed
- [ ] Unused `ArxivQuery` fields removed
- [ ] `utils/` directory deleted or moved to server
- [ ] Dead type-narrowing code removed
- [ ] All tests pass
- [ ] No broken imports

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-26 | Issue identified in code review | Multiple reviewers flagged same issues |
