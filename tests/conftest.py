"""Test setup for arxiv2md."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for pytest.

    This allows running integration tests selectively:
        pytest -m integration       # run only integration tests
        pytest -m "not integration" # skip integration tests
    """
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (make real network calls)",
    )


@pytest.fixture
def network_timeout() -> float:
    """Default timeout for network operations in seconds."""
    return 60.0
