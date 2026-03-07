import json
import logging
import hashlib
from typing import Optional, Any
from abc import ABC, abstractmethod
from ..config import settings

logger = logging.getLogger("angel-claw-cache")

class BaseCache(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        pass

class RedisCache(BaseCache):
    def __init__(self):
        import redis.asyncio as redis
        self._redis = redis.from_url(settings.redis_url)
        self._ttl = settings.cache_ttl

    def _hash_key(self, key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    async def get(self, key: str) -> Optional[Any]:
        hashed = self._hash_key(key)
        data = await self._redis.get(f"cache:{hashed}")
        if data:
            return json.loads(data)
        return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        hashed = self._hash_key(key)
        await self._redis.set(
            f"cache:{hashed}", 
            json.dumps(value), 
            ex=ttl or self._ttl
        )

def get_cache() -> Optional[BaseCache]:
    if settings.cache_enabled:
        try:
            return RedisCache()
        except Exception as e:
            logger.error(f"Failed to initialize Redis cache: {e}")
            return None
    return None

cache = get_cache()
