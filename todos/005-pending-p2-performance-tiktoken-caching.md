---
status: pending
priority: p2
issue_id: "005"
tags: [code-review, performance, library]
dependencies: []
---

# Cache tiktoken Encoder for Performance

## Problem Statement

The tiktoken encoder is re-initialized on every call to `_format_token_count()`, adding ~50-100ms latency per paper processed. The encoder loading involves disk I/O which also blocks the event loop.

## Findings

**Location**: `/home/rbw/repo/arxiv2md/src/arxiv2md/output_formatter.py` lines 127-134

```python
def _format_token_count(text: str) -> str | None:
    if not tiktoken:
        return None
    try:
        encoding = tiktoken.get_encoding("o200k_base")  # Re-created every call!
        total_tokens = len(encoding.encode(text, disallowed_special=()))
    except Exception:
        return None
```

**Impact**:
- 50-100ms overhead per paper
- Blocks event loop (synchronous file I/O)
- 100 papers = 5-10 seconds unnecessary overhead

## Proposed Solutions

### Option A: Module-Level Cached Encoder (Recommended)
- **Pros**: Single initialization, near-zero overhead on subsequent calls
- **Cons**: Uses module state
- **Effort**: Very small (3 lines)
- **Risk**: None

```python
_TIKTOKEN_ENCODING = None

def _get_encoder():
    global _TIKTOKEN_ENCODING
    if _TIKTOKEN_ENCODING is None and tiktoken:
        _TIKTOKEN_ENCODING = tiktoken.get_encoding("o200k_base")
    return _TIKTOKEN_ENCODING

def _format_token_count(text: str) -> str | None:
    encoding = _get_encoder()
    if encoding is None:
        return None
    try:
        total_tokens = len(encoding.encode(text, disallowed_special=()))
    except Exception:
        return None
    # ... rest of function
```

### Option B: Lazy Initialization with functools.lru_cache
- **Pros**: Cleaner syntax
- **Cons**: Slight overhead from lru_cache
- **Effort**: Very small
- **Risk**: None

```python
@functools.lru_cache(maxsize=1)
def _get_encoder():
    return tiktoken.get_encoding("o200k_base") if tiktoken else None
```

## Recommended Action

Option A or B - both are acceptable. Option B is slightly cleaner.

## Technical Details

**Affected files**:
- `src/arxiv2md/output_formatter.py`

**Performance improvement**: ~50-100ms per paper (after first call)

## Acceptance Criteria

- [ ] tiktoken encoder is cached after first use
- [ ] Token counting still works correctly
- [ ] Performance improvement measurable

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-26 | Issue identified in code review | Performance agent flagged |
