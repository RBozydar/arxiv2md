---
status: pending
priority: p2
issue_id: "007"
tags: [code-review, type-safety, library]
dependencies: []
---

# Use Literal Type for Filter Mode Parameter

## Problem Statement

The `mode` parameter in `filter_sections()` accepts any string but only handles "include" and "exclude", losing type safety that would catch typos at type-check time.

## Findings

**Location**: `/home/rbw/repo/arxiv2md/src/arxiv2md/sections.py` lines 18-23

```python
def filter_sections(
    sections: list[SectionNode],
    *,
    mode: str = "exclude",  # Should be Literal["include", "exclude"]
    selected: Iterable[str] | None = None,
) -> list[SectionNode]:
```

**Contrast with**: `IngestionOptions` in `ingestion.py` correctly uses:
```python
section_filter_mode: Literal["include", "exclude"] = "exclude"
```

**Issue**: Inconsistent type safety. A typo like `mode="inclde"` would silently fall through to exclude mode.

## Proposed Solutions

### Option A: Add Literal Type (Recommended)
- **Pros**: Type safety, IDE autocomplete, catches typos
- **Cons**: None
- **Effort**: Very small
- **Risk**: None

```python
from typing import Literal

def filter_sections(
    sections: list[SectionNode],
    *,
    mode: Literal["include", "exclude"] = "exclude",
    selected: Iterable[str] | None = None,
) -> list[SectionNode]:
```

## Recommended Action

Option A - Add `Literal["include", "exclude"]` type annotation.

## Technical Details

**Affected files**:
- `src/arxiv2md/sections.py`

**Import needed**: `from typing import Literal`

## Acceptance Criteria

- [ ] `mode` parameter typed as `Literal["include", "exclude"]`
- [ ] mypy passes
- [ ] Tests still pass

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-26 | Issue identified in code review | Baseline reviewer flagged |
