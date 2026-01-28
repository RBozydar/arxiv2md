---
status: pending
priority: p1
issue_id: "001"
tags: [code-review, bug, library]
dependencies: []
---

# Mutation of Input Data in `filter_sections`

## Problem Statement

The `filter_sections()` function mutates its input `SectionNode` objects by directly modifying their `children` attribute. This is a bug because:
- Callers may not expect their data to be modified
- Calling `filter_sections` twice with different modes corrupts the data
- Makes the function non-idempotent and hard to reason about

## Findings

**Location**: `/home/rbw/repo/arxiv2md/src/arxiv2md/sections.py` lines 38-46

```python
def _filter(nodes: list[SectionNode]) -> list[SectionNode]:
    result: list[SectionNode] = []
    for node in nodes:
        normalized = normalize_section_title(node.title)
        in_selected = normalized in selected_titles
        if mode == "include":
            if in_selected:
                result.append(node)
            else:
                children = _filter(node.children)
                if children:
                    node.children = children  # MUTATES INPUT!
                    result.append(node)
        else:
            if in_selected:
                continue
            node.children = _filter(node.children)  # MUTATES INPUT!
            result.append(node)
    return result
```

**Impact**: Data corruption when the same sections are filtered multiple times with different parameters.

## Proposed Solutions

### Option A: Create New SectionNode Instances (Recommended)
- **Pros**: Clean, immutable-friendly, safe
- **Cons**: More memory allocation
- **Effort**: Small
- **Risk**: Low

```python
def _filter(nodes: list[SectionNode]) -> list[SectionNode]:
    result: list[SectionNode] = []
    for node in nodes:
        normalized = normalize_section_title(node.title)
        in_selected = normalized in selected_titles
        if mode == "include":
            if in_selected:
                result.append(node.model_copy(deep=True))
            else:
                children = _filter(node.children)
                if children:
                    new_node = node.model_copy(update={"children": children})
                    result.append(new_node)
        else:
            if in_selected:
                continue
            new_children = _filter(node.children)
            new_node = node.model_copy(update={"children": new_children})
            result.append(new_node)
    return result
```

### Option B: Deep Copy Input at Start
- **Pros**: Simple implementation
- **Cons**: Copies entire tree even if few changes needed
- **Effort**: Very small
- **Risk**: Low

## Recommended Action

Option A - Create new `SectionNode` instances during filtering to avoid mutation.

## Technical Details

**Affected files**:
- `src/arxiv2md/sections.py`

**Related code**:
- `ingestion.py` calls `filter_sections()` potentially multiple times (once for user sections, once for references)

## Acceptance Criteria

- [ ] `filter_sections()` does not modify input `SectionNode` objects
- [ ] Calling `filter_sections()` twice on same input with different modes works correctly
- [ ] Existing tests pass
- [ ] Add test verifying input is not mutated

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-26 | Issue identified in code review | Found by multiple reviewers |
