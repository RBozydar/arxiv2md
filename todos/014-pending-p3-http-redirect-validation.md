---
status: pending
priority: p3
issue_id: "014"
tags: [code-review, security, library]
dependencies: []
---

# Consider Validating HTTP Redirect Destinations

## Problem Statement

The HTTP client follows redirects automatically. While initial URLs are validated against the allowlist, redirects could potentially lead to non-arXiv hosts if arXiv servers were compromised or misconfigured.

## Findings

**Location**: `/home/rbw/repo/arxiv2md/src/arxiv2md/http_utils.py` lines 84-89

```python
async with httpx.AsyncClient(
    timeout=timeout,
    headers=headers,
    follow_redirects=True,  # Follows redirects automatically
    max_redirects=_MAX_REDIRECTS,  # Max 5
) as new_client:
```

**Risk Assessment**: LOW
- arXiv servers are unlikely to redirect to malicious hosts
- This is defense-in-depth, not a critical vulnerability
- Would require httpx event hooks to implement

## Proposed Solutions

### Option A: Validate Redirect Destinations
- **Pros**: Defense in depth
- **Cons**: Complex implementation with httpx
- **Effort**: Medium
- **Risk**: Low

Would require implementing a custom event hook:
```python
async def check_redirect(request):
    if request.url.host not in _ALLOWED_HOSTS:
        raise FetchError(f"Redirect to disallowed host: {request.url.host}")

# Use in client config
```

### Option B: Document as Accepted Risk
- **Pros**: No implementation needed
- **Cons**: Theoretical risk remains
- **Effort**: None
- **Risk**: Low (accepted)

## Recommended Action

Option B for now - document as accepted risk. The attack surface is minimal (requires compromised arXiv servers), and implementation is complex.

## Technical Details

**Affected files** (if implementing):
- `src/arxiv2md/http_utils.py`

## Acceptance Criteria

- [ ] Decision documented in code comments
- [ ] OR redirect validation implemented

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-26 | Issue identified in code review | Security sentinel flagged as low risk |
