---
status: pending
priority: p1
issue_id: "003"
tags: [code-review, security, reliability, library]
dependencies: []
---

# Subprocess Without Timeout in Pandoc Conversion

## Problem Statement

The pandoc subprocess in `convert_latex_to_markdown()` has no timeout, meaning a malicious or very large LaTeX file could hang the process indefinitely.

## Findings

**Location**: `/home/rbw/repo/arxiv2md/src/arxiv2md/latex_parser.py` lines 66-72

```python
result = subprocess.run(
    ["pandoc", tex_filename, "-f", "latex", "-t", "markdown", "--wrap=none"],
    cwd=source_dir,
    capture_output=True,
    text=True,
    check=False,
)
```

**Risk**: Denial of service if pandoc hangs on malformed input. In server context, this could exhaust worker threads.

## Proposed Solutions

### Option A: Add Configurable Timeout (Recommended)
- **Pros**: Prevents hangs, configurable via environment
- **Cons**: May need tuning for very large papers
- **Effort**: Small
- **Risk**: Low (might timeout on legitimate large papers, but better than hanging)

```python
# In config.py
DEFAULT_PANDOC_TIMEOUT_S = 300  # 5 minutes
ARXIV2MD_PANDOC_TIMEOUT_S = int(os.getenv("ARXIV2MD_PANDOC_TIMEOUT_S", str(DEFAULT_PANDOC_TIMEOUT_S)))

# In latex_parser.py
from arxiv2md.config import ARXIV2MD_PANDOC_TIMEOUT_S

result = subprocess.run(
    ["pandoc", tex_filename, "-f", "latex", "-t", "markdown", "--wrap=none"],
    cwd=source_dir,
    capture_output=True,
    text=True,
    check=False,
    timeout=ARXIV2MD_PANDOC_TIMEOUT_S,
)
```

### Option B: Fixed Timeout
- **Pros**: Simpler
- **Cons**: Not configurable
- **Effort**: Very small
- **Risk**: Low

## Recommended Action

Option A - Add configurable timeout (default 300 seconds).

## Technical Details

**Affected files**:
- `src/arxiv2md/latex_parser.py`
- `src/arxiv2md/config.py` (add constant)

**Exception handling**: `subprocess.TimeoutExpired` should be caught and wrapped in `ConversionError`.

## Acceptance Criteria

- [ ] `subprocess.run()` has `timeout` parameter
- [ ] Timeout is configurable via environment variable
- [ ] `subprocess.TimeoutExpired` is caught and converted to `ConversionError`
- [ ] Reasonable default timeout (300s suggested)

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-01-26 | Issue identified in code review | Security and reliability concern |
