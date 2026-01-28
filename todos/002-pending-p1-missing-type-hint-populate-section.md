---
status: pending
priority: p1
issue_id: "002"
tags: [code-review, type-safety, library]
dependencies: []
---

# Missing Type Hint on `_populate_section_markdown`

## Problem Statement

The `section` parameter in `_populate_section_markdown()` has no type hint, violating the codebase's 100% type annotation coverage standard.

## Findings

**Location**: `/home/rbw/repo/arxiv2md/src/arxiv2md/ingestion.py` lines 238-239

```python
def _populate_section_markdown(
    section, *, remove_inline_citations: bool = False  # Missing type hint!
) -> None:
```

**Expected**:
```python
def _populate_section_markdown(
    section: SectionNode, *, remove_inline_citations: bool = False
) -> None:
```

## Proposed Solutions

### Option A: Add Type Hint (Recommended)
- **Pros**: Maintains type safety, enables IDE support
- **Cons**: None
- **Effort**: Very small (1 line change)
- **Risk**: None

## Recommended Action

Add type hint `section: SectionNode`.

## Technical Details

**Affected files**:
- `src/arxiv2md/ingestion.py`

**Required import**: `SectionNode` is already available via `from arxiv2md.schemas import SectionNode` or can use string annotation.

## Acceptance Criteria

- [ ] `section` parameter has type hint `SectionNode`
- [ ] mypy passes without errors

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-26 | Issue identified in code review | Only missing type hint in codebase |
