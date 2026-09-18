"""
backend/app/core/logging_config.py

Phase 9A — Centralized Structured Logging Configuration.
Sets up structured logging for FastAPI, database operations, RAG retrieval, and Risk Engine:
- Formats logs in clean JSON/KV layout with ISO timestamps.
- Records request processing latency, DB query timing, and cache hit metrics.
- Preserves full internal tracebacks for diagnostics while ensuring sensitive details
  are never leaked to HTTP response payloads.
"""

import sys
import logging
import json
import time
from typing import Any, Dict


class StructuredJSONFormatter(logging.Formatter):
    """JSON log formatter for structured observability."""
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt or "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage()
        }

        # Include additional extra attributes if provided
        if hasattr(record, "duration_ms"):
            log_obj["duration_ms"] = getattr(record, "duration_ms")
        if hasattr(record, "route"):
            log_obj["route"] = getattr(record, "route")
        if hasattr(record, "status_code"):
            log_obj["status_code"] = getattr(record, "status_code")
        if hasattr(record, "cache_hit"):
            log_obj["cache_hit"] = getattr(record, "cache_hit")

        # Capture exception traceback internally if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_logging(log_level: str = "INFO"):
    """Initialize structured logging across the FastAPI application."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(StructuredJSONFormatter())
    root_logger.addHandler(console_handler)

    # Silence overly verbose third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logger = logging.getLogger("nirman.system")
    logger.info("Structured logging framework initialized successfully.")
    return logger


logger = logging.getLogger("nirman.app")
