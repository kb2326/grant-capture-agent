"""Logging for the ingest CLI. HTTP client loggers print full request URLs (including
query-string API keys such as SAM.gov's), so they are capped at WARNING."""

import logging


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level)
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
