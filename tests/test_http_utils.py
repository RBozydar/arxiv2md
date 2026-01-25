"""Tests for HTTP utilities module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from arxiv2md.exceptions import FetchError
from arxiv2md.http_utils import RETRY_STATUS_CODES, fetch_with_retries


class TestRetryStatusCodes:
    """Tests for RETRY_STATUS_CODES constant."""

    def test_contains_expected_codes(self) -> None:
        """Should contain all expected retryable status codes."""
        expected = {429, 500, 502, 503, 504}
        assert RETRY_STATUS_CODES == frozenset(expected)

    def test_is_immutable(self) -> None:
        """Should be a frozenset (immutable)."""
        assert isinstance(RETRY_STATUS_CODES, frozenset)


class TestFetchWithRetries:
    """Tests for fetch_with_retries function."""

    @pytest.mark.asyncio
    async def test_returns_text_by_default(self) -> None:
        """Returns text content when return_bytes=False (default)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>test content</html>"
        mock_response.raise_for_status = MagicMock()

        with patch("arxiv2md.http_utils.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await fetch_with_retries("https://example.com")

        assert result == "<html>test content</html>"
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_returns_bytes_when_requested(self) -> None:
        """Returns bytes content when return_bytes=True."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"binary content"
        mock_response.raise_for_status = MagicMock()

        with patch("arxiv2md.http_utils.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await fetch_with_retries("https://example.com", return_bytes=True)

        assert result == b"binary content"
        assert isinstance(result, bytes)

    @pytest.mark.asyncio
    async def test_raises_on_404_with_default_message(self) -> None:
        """Raises FetchError on 404 with default message."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("arxiv2md.http_utils.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(FetchError, match="Resource not found"):
                await fetch_with_retries("https://example.com/notfound")

    @pytest.mark.asyncio
    async def test_raises_on_404_with_custom_message(self) -> None:
        """Raises FetchError on 404 with custom message."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("arxiv2md.http_utils.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(FetchError, match="Custom 404 message"):
                await fetch_with_retries(
                    "https://example.com",
                    on_404_message="Custom 404 message",
                )

    @pytest.mark.asyncio
    async def test_raises_custom_exception_on_404(self) -> None:
        """Raises custom exception class on 404 when specified."""

        class CustomError(Exception):
            pass

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("arxiv2md.http_utils.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(CustomError):
                await fetch_with_retries(
                    "https://example.com",
                    on_404=CustomError,
                    on_404_message="Custom error",
                )

    @pytest.mark.asyncio
    async def test_retries_on_503(self) -> None:
        """Retries on 503 status code."""
        fail_response = MagicMock()
        fail_response.status_code = 503

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.text = "success"
        success_response.raise_for_status = MagicMock()

        with (
            patch("arxiv2md.http_utils.ARXIV2MD_FETCH_MAX_RETRIES", 2),
            patch("arxiv2md.http_utils.ARXIV2MD_FETCH_BACKOFF_S", 0.01),
            patch("arxiv2md.http_utils.httpx.AsyncClient") as mock_client_class,
        ):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=[fail_response, success_response])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await fetch_with_retries("https://example.com")

        assert result == "success"
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self) -> None:
        """Raises FetchError after exhausting retries."""
        fail_response = MagicMock()
        fail_response.status_code = 503

        with (
            patch("arxiv2md.http_utils.ARXIV2MD_FETCH_MAX_RETRIES", 2),
            patch("arxiv2md.http_utils.ARXIV2MD_FETCH_BACKOFF_S", 0.01),
            patch("arxiv2md.http_utils.httpx.AsyncClient") as mock_client_class,
        ):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=fail_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(FetchError, match="Failed to fetch"):
                await fetch_with_retries("https://example.com")

            # Initial attempt + 2 retries = 3 total
            assert mock_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_retries_on_request_error(self) -> None:
        """Retries on network request errors."""
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.text = "success"
        success_response.raise_for_status = MagicMock()

        with (
            patch("arxiv2md.http_utils.ARXIV2MD_FETCH_MAX_RETRIES", 2),
            patch("arxiv2md.http_utils.ARXIV2MD_FETCH_BACKOFF_S", 0.01),
            patch("arxiv2md.http_utils.httpx.AsyncClient") as mock_client_class,
        ):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=[
                    httpx.RequestError("Connection failed"),
                    success_response,
                ]
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await fetch_with_retries("https://example.com")

        assert result == "success"

    @pytest.mark.asyncio
    async def test_uses_provided_client(self) -> None:
        """Uses provided httpx.AsyncClient if passed."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "success"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await fetch_with_retries("https://example.com", client=mock_client)

        assert result == "success"
        mock_client.get.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_client_has_correct_settings(self) -> None:
        """Creates client with correct timeout and redirect settings."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "success"
        mock_response.raise_for_status = MagicMock()

        with patch("arxiv2md.http_utils.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await fetch_with_retries("https://example.com")

            # Verify client was created with correct settings
            call_kwargs = mock_client_class.call_args[1]
            assert call_kwargs["follow_redirects"] is True
            assert call_kwargs["max_redirects"] == 5
            assert "timeout" in call_kwargs
            assert "headers" in call_kwargs
