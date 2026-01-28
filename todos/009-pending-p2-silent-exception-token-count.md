---
status: pending
priority: p2
issue_id: "009"
tags: [code-review, error-handling, library]
dependencies: []
---

# Silent Exception Swallowing in Token Counting

## Problem Statement

The `_format_token_count()` function catches all exceptions silently, which could mask real issues and makes debugging difficult.

## Findings

**Location**: `/home/rbw/repo/arxiv2md/src/arxiv2md/output_formatter.py` lines 133-134

```python
def _format_token_count(text: str) -> str | None:
    if not tiktoken:
        return None
    try:
        encoding = tiktoken.get_encoding("o200k_base")
        total_tokens = len(encoding.encode(text, disallowed_special=()))
    except Exception:  # Bare exception - swallows all errors!
        return None
```

**Issues**:
1. Bare `except Exception` catches programming errors, not just tiktoken issues
2. Errors are completely silent - no logging
3. Makes debugging very difficult

## Proposed Solutions

### Option A: Catch Specific Exceptions + Log (Recommended)
- **Pros**: Doesn't hide programming errors, provides debug info
- **Cons**: Need to identify tiktoken exception types
- **Effort**: Small
- **Risk**: Low

```python
import logging

logger = logging.getLogger(__name__)

def _format_token_count(text: str) -> str | None:
    if not tiktoken:
        return None
    try:
        encoding = tiktoken.get_encoding("o200k_base")
        total_tokens = len(encoding.encode(text, disallowed_special=()))
    except (KeyError, ValueError) as exc:
        # tiktoken can raise KeyError for unknown encoding or ValueError for invalid input
        logger.debug("Token counting failed: %s", exc)
        return None
```

### Option B: Keep Broad Catch but Add Logging
- **Pros**: Simple, maintains backward compat
- **Cons**: Still catches too much
- **Effort**: Very small
- **Risk**: Low

```python
except Exception as exc:
    logger.debug("Token counting failed: %s", exc)
    return None
```

## Recommended Action

Option A or B - at minimum add logging. Option A preferred for correctness.

## Technical Details

**Affected files**:
- `src/arxiv2md/output_formatter.py`

## Acceptance Criteria

- [ ] Exceptions are logged (at least at debug level)
- [ ] Consider narrowing exception types if possible
- [ ] Function still returns None on failure (graceful degradation)

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-26 | Issue identified in code review | Multiple reviewers flagged |
