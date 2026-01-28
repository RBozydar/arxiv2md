---
status: pending
priority: p2
issue_id: "006"
tags: [code-review, consistency, library]
dependencies: []
---

# Inconsistent Exception Handling on BeautifulSoup Import

## Problem Statement

The same error condition (missing BeautifulSoup) raises different exception types in different modules, making error handling inconsistent.

## Findings

**Locations**:

1. `/home/rbw/repo/arxiv2md/src/arxiv2md/html_parser.py` lines 16-19:
```python
except ImportError as exc:
    raise ParseError(
        "BeautifulSoup4 is required for HTML parsing (pip install beautifulsoup4)."
    ) from exc
```

2. `/home/rbw/repo/arxiv2md/src/arxiv2md/markdown.py` lines 11-13:
```python
except ImportError as exc:
    raise RuntimeError(
        "BeautifulSoup4 is required for HTML parsing (pip install beautifulsoup4)."
    ) from exc
```

3. `/home/rbw/repo/arxiv2md/src/arxiv2md/html_utils.py` lines 11-13:
```python
except ImportError as exc:
    raise RuntimeError(
        "BeautifulSoup4 is required for HTML parsing (pip install beautifulsoup4)."
    ) from exc
```

**Issue**: `html_parser.py` uses `ParseError` while `markdown.py` and `html_utils.py` use `RuntimeError`.

## Proposed Solutions

### Option A: Use ParseError Consistently (Recommended)
- **Pros**: Uses existing custom exception, consistent with error hierarchy
- **Cons**: None
- **Effort**: Very small
- **Risk**: None

### Option B: Create DependencyError
- **Pros**: More semantic
- **Cons**: Adds another exception class
- **Effort**: Small
- **Risk**: Low

## Recommended Action

Option A - Use `ParseError` in all three locations.

## Technical Details

**Affected files**:
- `src/arxiv2md/markdown.py`
- `src/arxiv2md/html_utils.py`

**Changes needed**:
1. Import `ParseError` from `arxiv2md.exceptions`
2. Change `RuntimeError` to `ParseError`

## Acceptance Criteria

- [ ] All BeautifulSoup import errors raise same exception type
- [ ] Exception message is identical across all locations
- [ ] Tests still pass

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-26 | Issue identified in code review | Pattern analysis found inconsistency |
