"""
backend/app/services/cache_service.py

Phase 9A — In-Memory Thread-Safe TTL + LRU Cache Service.
Provides high-performance response caching for analytical and retrieval operations:
- Portfolio KPIs & Summaries
- Risk Intelligence Assessments
- Frequent RAG Hybrid Searches
- Executive Briefing Syntheses

NOTE FOR MULTI-INSTANCE DEPLOYMENTS:
This implementation utilizes an in-memory dictionary with thread safety suitable for single-instance
FastAPI deployments. For distributed multi-instance production deployments across multiple worker nodes,
this class should be swapped with a Redis-backed cache adapter using identical method contracts.
"""

import time
import threading
from typing import Any, Optional, Dict
from dataclasses import dataclass


@dataclass
class CacheItem:
    value: Any
    created_at: float
    expires_at: float
    last_accessed: float


class CacheService:
    def __init__(self, default_ttl_seconds: int = 300, max_size: int = 1000):
        self.default_ttl = default_ttl_seconds
        self.max_size = max_size
        self._cache: Dict[str, CacheItem] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a cached item if present and not expired."""
        with self._lock:
            item = self._cache.get(key)
            now = time.time()
            if item is None:
                self.misses += 1
                return None

            if now > item.expires_at:
                # Expired item
                del self._cache[key]
                self.misses += 1
                return None

            # Update access metadata
            item.last_accessed = now
            self.hits += 1
            return item.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set a cached item with optional custom TTL."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        now = time.time()
        expires_at = now + ttl

        with self._lock:
            # Enforce LRU eviction if capacity exceeded
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()

            self._cache[key] = CacheItem(
                value=value,
                created_at=now,
                expires_at=expires_at,
                last_accessed=now
            )

    def delete(self, key: str) -> bool:
        """Remove a specific key from cache (useful on data mutation)."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all cached items."""
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """Return operational cache statistics."""
        with self._lock:
            now = time.time()
            active_items = sum(1 for item in self._cache.values() if now <= item.expires_at)
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests) if total_requests > 0 else 0.0

            return {
                "active_items": active_items,
                "total_capacity": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate_percent": round(hit_rate * 100.0, 2),
                "default_ttl_seconds": self.default_ttl
            }

    def _evict_lru(self) -> None:

        """Evict the least recently accessed item from cache."""
        if not self._cache:
            return

        # Find key with earliest last_accessed timestamp
        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_accessed)
        del self._cache[lru_key]


# Global Singleton Cache Instance
cache_service = CacheService(default_ttl_seconds=300, max_size=1000)
