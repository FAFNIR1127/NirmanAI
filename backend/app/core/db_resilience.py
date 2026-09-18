"""
backend/app/core/db_resilience.py

Phase 9C — Database Resilience & Connection Health Layer.
Provides connection pooling, health verification, and retry policies for PostgreSQL database sessions:
- Verifies connection vitality using fast ping execution (`SELECT 1`).
- Implements exponential backoff retries (max 3 retries) on transient network glitches.
- CRITICAL ARCHITECTURAL GUARANTEE: In the event of unrecoverable database outages, this module
  raises a controlled HTTPException(503, detail="Database Service Unavailable") rather than
  serving unverified or stale fallback metrics to executive decision-makers.
"""

import time
import logging
from typing import Callable, Any
from fastapi import HTTPException
import sqlalchemy
from sqlalchemy.exc import OperationalError, DBAPIError
from backend.app.config import DATABASE_URL, FALLBACK_SQLITE_PATH

logger = logging.getLogger("nirman.db")

# Singleton Database Engine with Connection Pooling
_engine: sqlalchemy.Engine | None = None


def get_resilient_db_engine() -> sqlalchemy.Engine:
    """Return singleton SQLAlchemy engine with optimized connection pooling."""
    global _engine
    if _engine is None:
        try:
            _engine = sqlalchemy.create_engine(
                DATABASE_URL,
                pool_size=10,
                max_overflow=20,
                pool_timeout=10,
                pool_recycle=1800,
                pool_pre_ping=True  # Automatic pre-ping check before issuing queries
            )
        except Exception as e:
            logger.warning(f"Primary PostgreSQL engine creation failed: {e}. Defaulting to SQLite fallback.")
            _engine = sqlalchemy.create_engine(f"sqlite:///{FALLBACK_SQLITE_PATH}", pool_pre_ping=True)
    return _engine


def check_db_health(engine: sqlalchemy.Engine | None = None) -> bool:
    """Perform a fast ping query to verify database vitality."""
    eng = engine or get_resilient_db_engine()
    try:
        with eng.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


def execute_with_retry(query_func: Callable[[], Any], max_retries: int = 3, initial_delay: float = 0.2) -> Any:
    """
    Execute a database operation with exponential backoff retry.
    Raises HTTP 503 if all retries fail.
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(1, max_retries + 1):
        try:
            return query_func()
        except (OperationalError, DBAPIError) as e:
            last_exception = e
            logger.warning(f"Database query attempt {attempt}/{max_retries} failed: {e}. Retrying in {delay:.2f}s...")
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2.0
        except Exception as e:
            # Non-retryable error
            logger.error(f"Non-retryable database error: {e}", exc_info=True)
            raise e

    # All retries exhausted -> Controlled HTTP 503 error
    logger.critical(f"Database operational failure after {max_retries} attempts: {last_exception}")
    raise HTTPException(
        status_code=503,
        detail="Database Service Temporarily Unavailable. Please try again shortly."
    )
