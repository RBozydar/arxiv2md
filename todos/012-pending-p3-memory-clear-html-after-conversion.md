---
status: pending
priority: p3
issue_id: "012"
tags: [code-review, performance, memory, library]
dependencies: []
---

# Clear HTML After Markdown Conversion to Save Memory

## Problem Statement

`SectionNode` objects retain both `html` and `markdown` content simultaneously, doubling memory usage for content storage.

## Findings

**Location**: `/home/rbw/repo/arxiv2md/src/arxiv2md/schemas/sections.py` lines 8-16

```python
class SectionNode(BaseModel):
    title: str
    level: int = Field(..., ge=1, le=6)
    anchor: str | None = None
    html: str | None = None       # Raw HTML retained
    markdown: str | None = None   # Converted markdown also retained
    children: list["SectionNode"] = Field(default_factory=list)
```

**Impact**:
- A paper with 50 sections averaging 10KB each = ~1MB duplication
- Not critical for CLI, but matters for server with concurrent requests

## Proposed Solutions

### Option A: Clear HTML After Conversion (Recommended)
- **Pros**: Halves memory usage per section, simple change
- **Cons**: Cannot re-convert after initial conversion
- **Effort**: Very small (1 line)
- **Risk**: Low

In `ingestion.py`:
```python
def _populate_section_markdown(section: SectionNode, *, remove_inline_citations: bool = False) -> None:
    if section.html:
        section.markdown = convert_fragment_to_markdown(
            section.html, remove_inline_citations=remove_inline_citations
        )
        section.html = None  # Release memory after conversion
    for child in section.children:
        _populate_section_markdown(child, remove_inline_citations=remove_inline_citations)
```

### Option B: Keep Both for Flexibility
- **Pros**: Can re-convert with different options
- **Cons**: Higher memory usage
- **Effort**: None
- **Risk**: None

## Recommended Action

Option A - Clear `html` field after conversion since it's not needed afterward.

## Technical Details

**Affected files**:
- `src/arxiv2md/ingestion.py`

**Memory improvement**: ~50% reduction in section content storage

## Acceptance Criteria

- [ ] `section.html` set to `None` after markdown conversion
- [ ] Output remains correct
- [ ] Tests pass

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-26 | Issue identified in code review | Performance oracle flagged |
