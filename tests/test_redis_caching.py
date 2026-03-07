import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from angel_claw.runtime.cache import RedisCache

class TestRedisCaching(unittest.IsolatedAsyncioTestCase):
    @patch('redis.asyncio.from_url')
    @patch('angel_claw.config.settings')
    async def test_cache_get_set(self, mock_settings, mock_redis_from_url):
        # Setup mock redis
        mock_redis = AsyncMock()
        mock_redis_from_url.return_value = mock_redis
        mock_settings.cache_ttl = 3600
        
        cache = RedisCache()
        test_key = "test_query"
        test_value = {"content": "Hello", "tool_calls": None}
        
        # Test Set
        await cache.set(test_key, test_value)
        mock_redis.set.assert_called_once()
        args = mock_redis.set.call_args[0]
        self.assertTrue(args[0].startswith("cache:"))
        self.assertEqual(json.loads(args[1]), test_value)
        
        # Test Get
        mock_redis.get.return_value = json.dumps(test_value)
        res = await cache.get(test_key)
        self.assertEqual(res, test_value)
        mock_redis.get.assert_called_once()

if __name__ == "__main__":
    unittest.main()
