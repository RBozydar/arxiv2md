"""Custom exceptions for arxiv2md."""


class Arxiv2mdError(Exception):
    """Base exception for arxiv2md operations."""


class FetchError(Arxiv2mdError):
    """Error during content fetching."""


class HTMLNotAvailableError(FetchError):
    """Paper does not have HTML version available."""


class SourceNotAvailableError(FetchError):
    """Paper source files are not available."""


class RateLimitError(FetchError):
    """Rate limited by arXiv."""


class ParseError(Arxiv2mdError):
    """Error during content parsing."""


class ConversionError(Arxiv2mdError):
    """Error during format conversion."""


class ExtractionError(Arxiv2mdError):
    """Error during source bundle extraction."""
