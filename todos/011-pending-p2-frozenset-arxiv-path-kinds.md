---
status: pending
priority: p2
issue_id: "011"
tags: [code-review, consistency, library]
dependencies: []
---

# Inconsistent Use of frozenset for Constants

## Problem Statement

`_ARXIV_PATH_KINDS` is a mutable `set` while `_ALLOWED_HOSTS` is a `frozenset`. Constants should be immutable.

## Findings

**Location**: `/home/rbw/repo/arxiv2md/src/arxiv2md/query_parser.py` lines 13-15

```python
_ARXIV_HOST: Final = "arxiv.org"
_ALLOWED_HOSTS: Final = frozenset({"arxiv.org", "www.arxiv.org"})  # Good!
_ARXIV_PATH_KINDS: Final = {"abs", "pdf", "html"}  # Mutable set - should be frozenset
```

**Issue**: `_ARXIV_PATH_KINDS` is marked as `Final` but is a mutable set. While `Final` prevents reassignment, the set contents could theoretically be modified.

## Proposed Solutions

### Option A: Use frozenset (Recommended)
- **Pros**: Truly immutable, consistent with `_ALLOWED_HOSTS`
- **Cons**: None
- **Effort**: Very small (1 character change)
- **Risk**: None

```python
_ARXIV_PATH_KINDS: Final = frozenset({"abs", "pdf", "html"})
```

## Recommended Action

Option A - Change to `frozenset`.

## Technical Details

**Affected files**:
- `src/arxiv2md/query_parser.py`

## Acceptance Criteria

- [ ] `_ARXIV_PATH_KINDS` is a `frozenset`
- [ ] Tests pass

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-26 | Issue identified in code review | Python reviewer flagged |
