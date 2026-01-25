"""Query model for arXiv ingestion."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from pydantic import BaseModel


class ArxivQuery(BaseModel):
    """Parsed arXiv query details.

    Contains the parsed arXiv identifier and associated URLs. Processing options
    are handled separately by IngestionOptions.

    Attributes:
        input_text: The original input text provided by the user.
        arxiv_id: The extracted arXiv paper identifier.
        version: Optional version string (e.g., "v1").
        html_url: Primary HTML URL (arxiv.org).
        ar5iv_url: Fallback ar5iv HTML URL.
        latex_url: LaTeX source URL.
        abs_url: Abstract page URL.
        id: Unique identifier for this query (used for caching).
        cache_dir: Directory path for caching this query's results.
    """

    input_text: str
    arxiv_id: str
    version: str | None = None
    html_url: str
    ar5iv_url: str
    latex_url: str
    abs_url: str
    id: UUID
    cache_dir: Path
