"""
Cache Service — Redis caching with graceful fallback.

If Redis is not available, all operations silently degrade
to direct computation (no caching).
"""

import json
from typing import Any, Optional

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)

# Try to import Redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class CacheService:
    """
    Redis-backed caching with graceful degradation.

    Usage:
        CacheService.set("key", value, ttl=300)
        value = CacheService.get("key")
    """

    _client = None
    _stats = {"hits": 0, "misses": 0}
    _enabled = False

    @classmethod
    def _get_client(cls):
        """Get or create Redis client."""
        if cls._client is not None:
            return cls._client

        if not REDIS_AVAILABLE:
            return None

        try:
            cls._client = redis.Redis(
                host="localhost",
                port=6379,
                db=0,
                socket_connect_timeout=2,
                decode_responses=True,
            )
            cls._client.ping()
            cls._enabled = True
            logger.info("Redis cache connected")
            return cls._client

        except Exception as e:
            logger.warning(f"Redis not available — caching disabled: {e}")
            cls._client = None
            cls._enabled = False
            return None

    @classmethod
    def get(cls, key: str) -> Optional[Any]:
        """
        Retrieve a value from cache.

        Returns None if not found or Redis unavailable.
        """
        client = cls._get_client()
        if not client:
            cls._stats["misses"] += 1
            return None

        try:
            value = client.get(key)
            if value is not None:
                cls._stats["hits"] += 1
                return json.loads(value)
            else:
                cls._stats["misses"] += 1
                return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            cls._stats["misses"] += 1
            return None

    @classmethod
    def set(cls, key: str, value: Any, ttl: int = 300):
        """
        Store a value in cache with TTL.

        Parameters
        ----------
        key : str
            Cache key.
        value : Any
            Value to store (must be JSON-serializable).
        ttl : int
            Time to live in seconds (default 5 minutes).
        """
        client = cls._get_client()
        if not client:
            return

        try:
            serialized = json.dumps(value, default=str)
            client.setex(key, ttl, serialized)
        except Exception as e:
            logger.error(f"Cache set error: {e}")

    @classmethod
    def delete(cls, key: str):
        """Delete a specific key from cache."""
        client = cls._get_client()
        if not client:
            return

        try:
            client.delete(key)
        except Exception as e:
            logger.error(f"Cache delete error: {e}")

    @classmethod
    def flush(cls):
        """Clear all cache."""
        client = cls._get_client()
        if not client:
            return

        try:
            client.flushdb()
            logger.info("Cache flushed")
        except Exception as e:
            logger.error(f"Cache flush error: {e}")

    @classmethod
    def get_analytics(cls, key: str) -> Optional[Any]:
        """Get cached analytics data."""
        return cls.get(f"analytics:{key}")

    @classmethod
    def cache_analytics(cls, key: str, value: Any, ttl: int = 1800):
        """Cache analytics data (default 30 min TTL)."""
        cls.set(f"analytics:{key}", value, ttl=ttl)

    @classmethod
    def get_stats(cls) -> dict:
        """Get cache hit/miss statistics."""
        total = cls._stats["hits"] + cls._stats["misses"]
        hit_rate = (cls._stats["hits"] / total * 100) if total > 0 else 0

        return {
            "enabled": cls._enabled,
            "hits": cls._stats["hits"],
            "misses": cls._stats["misses"],
            "hit_rate_percent": round(hit_rate, 1),
        }

    @classmethod
    def is_enabled(cls) -> bool:
        """Check if Redis caching is available."""
        cls._get_client()
        return cls._enabled
