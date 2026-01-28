---
status: pending
priority: p2
issue_id: "008"
tags: [code-review, simplification, library]
dependencies: []
---

# Inline html_utils.py into html_parser.py

## Problem Statement

The `html_utils.py` module contains a single function that is only used in `html_parser.py`. This adds an unnecessary file and import for minimal benefit.

## Findings

**Location**: `/home/rbw/repo/arxiv2md/src/arxiv2md/html_utils.py` (34 lines total)

Contains only one function `find_document_root()` called from:
- `html_parser.py` line 47
- `html_parser.py` line 71

Both calls are in the same file.

**Current code**:
```python
# html_utils.py (34 lines)
def find_document_root(soup: BeautifulSoup) -> Tag:
    """Find the main document root element in an arXiv HTML document."""
    root = soup.find("article", class_=re.compile(r"ltx_document"))
    if root:
        return root
    article = soup.find("article")
    if article:
        return article
    if soup.body:
        return soup.body
    return soup
```

## Proposed Solutions

### Option A: Move Function to html_parser.py (Recommended)
- **Pros**: Reduces file count, simplifies imports
- **Cons**: Slightly longer html_parser.py
- **Effort**: Very small
- **Risk**: None

### Option B: Keep as Separate Module
- **Pros**: May be useful for future utilities
- **Cons**: YAGNI violation, unnecessary indirection
- **Effort**: None
- **Risk**: None

## Recommended Action

Option A - Move `find_document_root()` to `html_parser.py` and delete `html_utils.py`.

## Technical Details

**Affected files**:
- `src/arxiv2md/html_utils.py` (delete)
- `src/arxiv2md/html_parser.py` (add function)

## Acceptance Criteria

- [ ] `html_utils.py` deleted
- [ ] `find_document_root()` moved to `html_parser.py`
- [ ] Import in `html_parser.py` updated
- [ ] Tests pass

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-26 | Issue identified in code review | YAGNI violation flagged |
