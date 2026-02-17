from typing import Any, Optional
import json
import redis.asyncio as aioredis
from app.core.config import REDIS_URL, REDIS_PASSWORD

class CookiesManager:
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None


    # ------------------------------------------------------------------
    # Redis Initialization
    # ------------------------------------------------------------------
    async def init_redis(self):
        if self.redis is None and REDIS_URL:
            self.redis = aioredis.from_url(
                REDIS_URL, password=REDIS_PASSWORD, decode_responses=True
            )

    async def ensure_redis(self):
        if self.redis is None:
            await self.init_redis()

  
    async def close_redis(self):
        if self.redis:
            await self.redis.close()
            self.redis = None
            
    # ------------------------------------------------------------------
    # Cache Management (UNCHANGED)
    # ------------------------------------------------------------------
    async def set_cache(self, key: str, value: Any, ttl: int = 60):
        await self.redis.setex(key, ttl, json.dumps(value))

    async def get_cache(self, key: str):
        result = await self.redis.get(key)
        return json.loads(result) if result else None            

    async def delete_cache(self, key: str):
        await self.redis.delete(key)    







_manager: Optional[CookiesManager] = None

def get_manager() -> CookiesManager:
    global _manager
    if _manager is None:
        _manager = CookiesManager()
    return _manager