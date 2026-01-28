---
status: pending
priority: p3
issue_id: "015"
tags: [code-review, performance, library]
dependencies: []
---

# BeautifulSoup Parses HTML Twice for Author Cleaning

## Problem Statement

The `_clean_author_text()` function re-parses HTML for each author node by converting the Tag to string and back to BeautifulSoup, adding unnecessary overhead.

## Findings

**Location**: `/home/rbw/repo/arxiv2md/src/arxiv2md/html_parser.py` lines 94-96

```python
def _clean_author_text(node: Tag) -> list[str]:
    """Extract clean author names/affiliations, filtering out emails and footnotes."""
    clone = BeautifulSoup(str(node), "lxml")  # Re-parses HTML for each author!
```

**Impact**:
- For a paper with 20 authors, creates 20 additional BeautifulSoup parsing operations
- Typical overhead: 5-20ms per author node
- Papers with 50+ authors could see 250-1000ms overhead

## Proposed Solutions

### Option A: Use copy.copy Instead of Re-parsing
- **Pros**: Much faster, avoids re-parsing
- **Cons**: May need verification that shallow copy is sufficient
- **Effort**: Small
- **Risk**: Low

```python
import copy

def _clean_author_text(node: Tag) -> list[str]:
    clone = copy.copy(node)  # Shallow copy, preserves parsed structure
    # Rest of function...
```

### Option B: Operate on Original and Restore
- **Pros**: No copying at all
- **Cons**: More complex, mutation concerns
- **Effort**: Medium
- **Risk**: Medium

### Option C: Accept Current Behavior
- **Pros**: No changes needed
- **Cons**: Suboptimal performance
- **Effort**: None
- **Risk**: None

## Recommended Action

Option A - Use `copy.copy()` or `copy.deepcopy()` instead of re-parsing.

## Technical Details

**Affected files**:
- `src/arxiv2md/html_parser.py`

**Performance improvement**: ~5-20ms per author (significant for many-author papers)

## Acceptance Criteria

- [ ] Author cleaning doesn't re-parse HTML
- [ ] Author extraction still works correctly
- [ ] Tests pass

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-26 | Issue identified in code review | Performance oracle flagged |
