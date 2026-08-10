# ruff: noqa: BLE001
import logging
import time

from upstash_redis import AsyncRedis

from app.core.config import settings

# Standard English docstring.
"""Upstash Redis Client with robust In-Memory Fallback.
Provides unified caching and rate limiting interface.
"""

logger = logging.getLogger(__name__)


class InMemoryCache:
    """Standard English docstring: In-memory fallback cache to ensure offline/local stability."""

    def __init__(self):
        # Hinglish explanation: Local caching ke liye key-value dictionary.
        self._cache: dict[str, tuple[str, float | None]] = {}
        # Hinglish explanation: Rate limit checks store karne ke liye key-value map.
        self._rate_limits: dict[str, tuple[int, float]] = {}

    async def get(self, key: str) -> str | None:
        # Hinglish explanation: Key ko retrieve karo aur check karo ki expire toh nahi ho gayi.
        if key in self._cache:
            val, expiry = self._cache[key]
            if expiry is None or expiry > time.time():
                return val
            else:
                del self._cache[key]
        return None

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        # Hinglish explanation: Key and value ko memory dictionary mein save karo with TTL.
        expiry = time.time() + ex if ex else None
        self._cache[key] = (value, expiry)
        return True

    async def setex(self, key: str, seconds: int, value: str) -> bool:
        return await self.set(key, value, ex=seconds)

    async def delete(self, key: str) -> bool:
        # Hinglish explanation: Key exist karti hai toh cache map se remove karo.
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    async def exists(self, key: str) -> int:
        val = await self.get(key)
        return 1 if val is not None else 0

    async def incr(self, key: str) -> int:
        # Hinglish explanation: Local window count increment karne ke liye algorithm.
        now = time.time()
        if key in self._rate_limits:
            count, expiry = self._rate_limits[key]
            if now < expiry:
                new_count = count + 1
                self._rate_limits[key] = (new_count, expiry)
                return new_count
        # Hinglish explanation: Expiry windows 60 seconds duration ki banayi jati hai.
        self._rate_limits[key] = (1, now + 60.0)
        return 1

    async def expire(self, key: str, seconds: int) -> bool:
        # Hinglish explanation: Rate limits window parameters update karne ke liye key adjust karo.
        if key in self._rate_limits:
            count, _ = self._rate_limits[key]
            self._rate_limits[key] = (count, time.time() + seconds)
            return True
        return False

    async def ping(self) -> bool:
        return True


class RedisClientWrapper:
    """Standard English docstring: Wrapper for AsyncRedis with automatic failover."""

    def __init__(self):
        # Hinglish explanation: Settings se values fetch karke credentials check karo.
        url = settings.UPSTASH_REDIS_URL
        token = settings.UPSTASH_REDIS_TOKEN

        self.is_configured = (
            url is not None
            and token is not None
            and url.strip() != ""
            and token.strip() != ""
            and "xxxxxxxx" not in url
            and "AXxxxxxxxx" not in token
            and url.startswith("https://")
        )

        self._redis: AsyncRedis | None = None
        self._fallback = InMemoryCache()

        if self.is_configured:
            try:
                # Hinglish explanation: Upstash Redis client initialize kiya ja raha hai.
                self._redis = AsyncRedis(url=url, token=token)
                logger.info("Upstash Redis connection initialized successfully.")
            except Exception as e:
                logger.warning(
                    f"Failed to initialize Upstash Redis: {e}. Falling back to in-memory mode."
                )
                self._redis = None
        else:
            logger.info("Upstash Redis not configured. Using in-memory fallback.")

    @property
    def active_client(self):
        # Hinglish explanation: Agar configured aur active hai toh redis return karo otherwise local memory.
        return self._redis if self._redis is not None else self._fallback

    async def get(self, key: str) -> str | None:
        try:
            return await self.active_client.get(key)
        except Exception as e:
            logger.error(f"Redis get failed: {e}. Falling back to in-memory.")
            return await self._fallback.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        try:
            # Hinglish explanation: AsyncRedis ka interface dictionary storage ke equal/compatible rakha hai.
            if self._redis is not None:
                await self._redis.set(key, value, ex=ex)
                return True
            return await self._fallback.set(key, value, ex=ex)
        except Exception as e:
            logger.error(f"Redis set failed: {e}. Falling back to in-memory.")
            return await self._fallback.set(key, value, ex=ex)

    async def setex(self, key: str, seconds: int, value: str) -> bool:
        try:
            if self._redis is not None:
                await self._redis.setex(key, seconds, value)
                return True
            return await self._fallback.setex(key, seconds, value)
        except Exception as e:
            logger.error(f"Redis setex failed: {e}. Falling back to in-memory.")
            return await self._fallback.setex(key, seconds, value)

    async def delete(self, key: str) -> bool:
        try:
            res = await self.active_client.delete(key)
            return bool(res)
        except Exception as e:
            logger.error(f"Redis delete failed: {e}. Falling back to in-memory.")
            return await self._fallback.delete(key)

    async def exists(self, key: str) -> int:
        try:
            return await self.active_client.exists(key)
        except Exception as e:
            logger.error(f"Redis exists failed: {e}. Falling back to in-memory.")
            return await self._fallback.exists(key)

    async def incr(self, key: str) -> int:
        try:
            return await self.active_client.incr(key)
        except Exception as e:
            logger.error(f"Redis incr failed: {e}. Falling back to in-memory.")
            return await self._fallback.incr(key)

    async def expire(self, key: str, seconds: int) -> bool:
        try:
            res = await self.active_client.expire(key, seconds)
            return bool(res)
        except Exception as e:
            logger.error(f"Redis expire failed: {e}. Falling back to in-memory.")
            return await self._fallback.expire(key, seconds)

    async def ping(self) -> bool:
        try:
            if self._redis is not None:
                await self._redis.ping()
                return True
            return True
        except Exception as e:
            logger.error(f"Redis ping failed: {e}.")
            return False


# Hinglish explanation: Single instance pure backend configuration cycle mein shared reuse hone ke liye.
redis_client = RedisClientWrapper()
