"""Centralized logging configuration for Zweitstimme.

This module provides a centralized logging system that:
- Uses consistent formatting across all modules
- Supports both console and file output
- Implements log rotation to prevent disk space issues
- Provides structured JSON logging for machine parsing
- Allows configuration via CLI arguments
"""

import json
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from pollingapi.core import settings


class StructuredLogFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if present
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class ColoredConsoleFormatter(logging.Formatter):
    """Colored formatter for console output."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format with colors for terminal output."""
        # Save original levelname
        original_levelname = record.levelname

        # Add color
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]
        record.levelname = f"{color}{record.levelname}{reset}"

        # Format the message
        result = super().format(record)

        # Restore original levelname
        record.levelname = original_levelname

        return result


def setup_logging(
    log_level: str = "INFO",
    log_dir: str | None = None,
    json_format: bool = False,
    console_colors: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> None:
    """Set up centralized logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files (default: data/logs/)
        json_format: Whether to use JSON formatting for file logs
        console_colors: Whether to use colors in console output
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
    """
    # Determine log directory
    log_path = settings.data_dir / "logs" if log_dir is None else Path(log_dir)

    log_path.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    root_logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))

    if console_colors and sys.stdout.isatty():
        console_format = "%(levelname)s: %(message)s"
        console_formatter = ColoredConsoleFormatter(console_format)
    else:
        console_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        console_formatter = logging.Formatter(console_format)

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler with rotation
    log_file = log_path / "zweitstimme.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)

    if json_format:
        file_formatter = StructuredLogFormatter()
    else:
        file_format = (
            "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
        )
        file_formatter = logging.Formatter(file_format)

    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Separate error log file
    error_file = log_path / "errors.log"
    error_handler = RotatingFileHandler(
        error_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_handler)

    # Scraper-specific log file
    scraper_file = log_path / "scraper.log"
    scraper_handler = RotatingFileHandler(
        scraper_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    scraper_handler.setLevel(logging.DEBUG)
    scraper_handler.setFormatter(file_formatter)

    # Create scraper logger
    scraper_logger = logging.getLogger("pollingapi.scraper")
    scraper_logger.setLevel(logging.DEBUG)
    scraper_logger.addHandler(scraper_handler)
    scraper_logger.propagate = False  # Don't propagate to root to avoid duplicates

    # Log startup message
    root_logger.info(f"Logging initialized - Level: {log_level}")
    root_logger.info(f"Log files: {log_path}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_scraper_event(
    logger: logging.Logger,
    event_type: str,
    worker_name: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Log a scraper event with structured data.

    Args:
        logger: Logger instance
        event_type: Type of event (e.g., 'fetch', 'parse', 'insert')
        worker_name: Name of the scraper worker
        details: Additional event details
    """
    log_data = {
        "event_type": event_type,
        "worker": worker_name,
        "timestamp": datetime.now().isoformat(),
    }

    if details:
        log_data.update(details)

    logger.info(f"Scraper event: {event_type}", extra={"extra_data": log_data})


class ScraperLogContext:
    """Context manager for scraper logging sessions.

    Usage:
        with ScraperLogContext(logger, "forsa") as ctx:
            ctx.log_start()
            # ... do scraping ...
            ctx.log_end(polls_inserted=42)
    """

    def __init__(self, logger: logging.Logger, worker_name: str):
        self.logger = logger
        self.worker_name = worker_name
        self.start_time: datetime | None = None

    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"[{self.worker_name}] Starting scraper")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = datetime.now() - self.start_time if self.start_time else None

        if exc_type:
            self.logger.error(
                f"[{self.worker_name}] Scraper failed after {duration}: {exc_val}",
                exc_info=(exc_type, exc_val, exc_tb),
            )
        else:
            self.logger.info(f"[{self.worker_name}] Scraper completed in {duration}")

        return False  # Don't suppress exceptions

    def log_progress(self, message: str, **kwargs):
        """Log a progress update."""
        self.logger.info(f"[{self.worker_name}] {message}", extra=kwargs)

    def log_metric(self, metric_name: str, value: Any):
        """Log a metric."""
        self.logger.info(
            f"[{self.worker_name}] Metric: {metric_name}={value}",
            extra={"metric": metric_name, "value": value},
        )
