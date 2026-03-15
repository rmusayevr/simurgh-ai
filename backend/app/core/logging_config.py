"""
Logging configuration for the application.

Provides structured logging with:
    - JSON format for production (machine-readable)
    - Colorized console output for development (human-readable)
    - Rotating file handlers to prevent disk space issues
    - Context injection (request IDs, user IDs, etc.)

Uses structlog for structured logging with stdlib integration.
"""

import logging
import sys
from pathlib import Path
from typing import List

import structlog
from logging.handlers import RotatingFileHandler

from app.core.config import settings


def configure_logging() -> None:
    """
    Configure application-wide logging.

    Behavior varies by environment:
        - Development: Colorized console output, verbose
        - Production: JSON logs, file rotation, structured

    Log outputs:
        - Console (stdout): Always enabled
        - File (logs/app.log): Optional, with rotation
    """
    # Determine log level from settings
    log_level = _get_log_level()

    # Setup log directory and file path
    log_file_path = _setup_log_directory()

    # Configure structlog processors
    processors = _get_structlog_processors()

    # Configure structlog
    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to avoid duplicates
    if root_logger.handlers:
        root_logger.handlers.clear()

    # Setup handlers
    handlers = _create_handlers(log_file_path)
    for handler in handlers:
        handler.setLevel(log_level)
        root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    _configure_third_party_loggers()

    # Log successful configuration
    logger = structlog.get_logger(__name__)
    logger.info(
        "logging_configured",
        level=log_level,
        format=settings.LOG_FORMAT,
        environment=settings.ENVIRONMENT,
        file_logging=log_file_path is not None,
    )


def _get_log_level() -> int:
    """
    Get log level from settings.

    Returns:
        int: Logging level constant (e.g., logging.INFO)
    """
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return level_map.get(settings.LOG_LEVEL.upper(), logging.INFO)


def _setup_log_directory() -> Path | None:
    """
    Create log directory and return log file path.

    Returns:
        Path: Path to log file, or None if file logging is disabled
    """
    # Skip file logging in certain environments or if disabled
    if settings.ENVIRONMENT == "test" or not settings.LOG_FORMAT:
        return None

    log_dir = Path("logs").resolve()

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"

        # Test write permissions
        test_file = log_dir / ".write_test"
        test_file.touch()
        test_file.unlink()

        return log_file
    except PermissionError as e:
        print(
            f"⚠️  Cannot create log directory {log_dir}: {e}\n"
            f"   File logging will be disabled. Console logging only.",
            file=sys.stderr,
        )
        return None
    except Exception as e:
        print(
            f"⚠️  Unexpected error setting up logs: {e}\n"
            f"   File logging will be disabled.",
            file=sys.stderr,
        )
        return None


def _get_structlog_processors() -> List:
    """
    Get structlog processors based on environment.

    Returns:
        list: Configured processors for structlog
    """
    # Shared processors (always included)
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Environment-specific processors
    if settings.LOG_FORMAT == "json" or settings.is_production:
        # Production: JSON format for log aggregation (ELK, Datadog, etc.)
        return shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Colorized console output for humans
        return shared_processors + [
            structlog.dev.ConsoleRenderer(
                colors=sys.stderr.isatty(),  # Only colorize if terminal supports it
                exception_formatter=structlog.dev.plain_traceback,
            )
        ]


def _create_handlers(log_file_path: Path | None) -> List[logging.Handler]:
    """
    Create logging handlers for console and file output.

    Args:
        log_file_path: Path to log file, or None to skip file logging

    Returns:
        list: Configured logging handlers
    """
    handlers = []

    # Console handler (always enabled)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    handlers.append(console_handler)

    # File handler (optional)
    if log_file_path:
        try:
            file_handler = RotatingFileHandler(
                filename=log_file_path,
                maxBytes=10 * 1024 * 1024,  # 10 MB per file
                backupCount=5,  # Keep 5 backup files (50 MB total)
                encoding="utf-8",
            )
            file_handler.setFormatter(logging.Formatter("%(message)s"))
            handlers.append(file_handler)
        except PermissionError as e:
            print(
                f"⚠️  Cannot write to log file {log_file_path}: {e}\n"
                f"   File logging disabled. Console logging only.",
                file=sys.stderr,
            )
        except Exception as e:
            print(
                f"⚠️  Error creating file handler: {e}\n   File logging disabled.",
                file=sys.stderr,
            )

    return handlers


def _configure_third_party_loggers() -> None:
    """
    Suppress or adjust log levels for noisy third-party libraries.

    Prevents log spam from libraries like SQLAlchemy, urllib3, etc.
    """
    # Suppress noisy loggers
    noisy_loggers = [
        "urllib3.connectionpool",  # HTTP request logs
        "asyncio",  # Asyncio debug logs
        "multipart.multipart",  # File upload logs
    ]

    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # SQLAlchemy: Show only warnings in production, info in development
    sqlalchemy_level = logging.WARNING if settings.is_production else logging.INFO
    logging.getLogger("sqlalchemy.engine").setLevel(sqlalchemy_level)

    # Celery: Reduce verbosity
    logging.getLogger("celery").setLevel(logging.WARNING)
    logging.getLogger("celery.worker").setLevel(logging.INFO)


def get_logger(name: str = None) -> structlog.BoundLogger:
    """
    Get a configured structlog logger.

    Args:
        name: Logger name (typically __name__ of calling module)

    Returns:
        structlog.BoundLogger: Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("user_login", user_id=123, ip="192.168.1.1")
    """
    return structlog.get_logger(name)


def bind_context(**kwargs) -> None:
    """
    Bind context variables to be included in all log messages.

    Useful for request-scoped context (request ID, user ID, etc.).

    Args:
        **kwargs: Key-value pairs to include in log context

    Example:
        >>> bind_context(request_id="abc-123", user_id=456)
        >>> logger.info("processing_request")
        # Output: {"request_id": "abc-123", "user_id": 456, "event": "processing_request"}
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """
    Clear all bound context variables.

    Should be called at the end of each request to prevent context leakage.

    Example:
        >>> clear_context()
    """
    structlog.contextvars.clear_contextvars()


def unbind_context(*keys: str) -> None:
    """
    Remove specific keys from context.

    Args:
        *keys: Keys to remove from context

    Example:
        >>> unbind_context("request_id", "user_id")
    """
    structlog.contextvars.unbind_contextvars(*keys)
