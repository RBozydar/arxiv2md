"""arxiv2md: ingest arXiv papers into Markdown."""

from arxiv2md.exceptions import (
    Arxiv2mdError,
    ConversionError,
    ExtractionError,
    FetchError,
    HTMLNotAvailableError,
    ParseError,
    RateLimitError,
    SourceNotAvailableError,
)
from arxiv2md.ingestion import IngestionOptions, ingest_paper
from arxiv2md.query_parser import parse_arxiv_input
from arxiv2md.schemas import ArxivQuery, IngestionResult

__all__ = [
    "Arxiv2mdError",
    "ArxivQuery",
    "ConversionError",
    "ExtractionError",
    "FetchError",
    "HTMLNotAvailableError",
    "IngestionOptions",
    "IngestionResult",
    "ParseError",
    "RateLimitError",
    "SourceNotAvailableError",
    "ingest_paper",
    "parse_arxiv_input",
]
