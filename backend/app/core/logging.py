"""
Structured logging setup.

We log as single-line, key=value-ish messages (not raw prints) so that in
production these lines can be ingested by any log aggregator (CloudWatch,
Datadog, etc.) without extra parsing work.

Rule from the spec (section 31): NEVER log passwords, API keys, or tokens.
Every log call in this codebase must be reviewed against that rule.
"""
import logging
import sys

from app.core.config import get_settings

settings = get_settings()


def configure_logging() -> None:
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [handler]

    # Quiet down noisy third-party loggers unless we're debugging
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DEBUG else logging.WARNING
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
