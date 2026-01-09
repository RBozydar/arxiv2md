"""Server module entry point for running with python -m server."""

import os

import uvicorn

# Import logging configuration first to intercept all logging
from arxiv2md.utils.logging_config import get_logger

logger = get_logger(__name__)

if __name__ == "__main__":
    # Get configuration from environment variables
    host = os.getenv("HOST", "0.0.0.0")  # noqa: S104
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"

    logger.info(
        "Starting arxiv2md server",
        extra={
            "host": host,
            "port": port,
        },
    )

    uvicorn.run(
        "server.main:app",
        host=host,
        port=port,
        reload=reload,
        log_config=None,  # Disable uvicorn's default logging config
    )
