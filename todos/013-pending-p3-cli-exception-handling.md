---
status: pending
priority: p3
issue_id: "013"
tags: [code-review, error-handling, cli]
dependencies: []
---

# Overly Broad Exception Handling in CLI

## Problem Statement

The CLI catches all `Exception` types, which can swallow programming bugs and make debugging difficult.

## Findings

**Location**: `/home/rbw/repo/arxiv2md/src/arxiv2md/__main__.py` lines 23-25

```python
def main() -> None:
    args = _parse_args()
    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
```

**Issue**: Bare `Exception` catches all errors including:
- `TypeError` from bugs
- `AttributeError` from bugs
- `KeyError` from bugs
- All expected `Arxiv2mdError` subclasses

## Proposed Solutions

### Option A: Catch Arxiv2mdError Specifically (Recommended)
- **Pros**: Programming bugs surface with full traceback
- **Cons**: Users see full traceback for unexpected errors
- **Effort**: Very small
- **Risk**: Low

```python
from arxiv2md.exceptions import Arxiv2mdError

def main() -> None:
    args = _parse_args()
    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        sys.exit(130)
    except Arxiv2mdError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    # Let other exceptions propagate with full traceback
```

### Option B: Add Debug Mode
- **Pros**: User-controllable verbosity
- **Cons**: More implementation
- **Effort**: Medium
- **Risk**: Low

```python
except Exception as exc:
    if args.debug:
        raise
    print(f"Error: {exc}", file=sys.stderr)
    sys.exit(1)
```

## Recommended Action

Option A - Catch `Arxiv2mdError` specifically. Unexpected errors should show full traceback.

## Technical Details

**Affected files**:
- `src/arxiv2md/__main__.py`

## Acceptance Criteria

- [ ] CLI catches `Arxiv2mdError` specifically
- [ ] Programming bugs show full traceback
- [ ] Expected errors show clean message

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-26 | Issue identified in code review | Multiple reviewers flagged |
