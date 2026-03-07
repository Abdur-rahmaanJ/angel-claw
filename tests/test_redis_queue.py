import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from angel_claw.lane_queue.queue import RedisLaneQueue
from angel_claw.lane_queue.task import Task

class TestRedisQueue(unittest.IsolatedAsyncioTestCase):
    @patch('redis.asyncio.from_url')
    async def test_enqueue(self, mock_redis_from_url):
        # Setup mock redis
        mock_redis = AsyncMock()
        mock_redis_from_url.return_value = mock_redis
        
        queue = RedisLaneQueue()
        task = Task(lane_key="test_lane", data={"test": "data"})
        
        await queue.enqueue(task)
        
        # Verify lpush was called with serialized task data
        mock_redis.lpush.assert_called_once()
        args = mock_redis.lpush.call_args[0]
        self.assertEqual(args[0], "angel_claw_lane_queue")
        enqueued_data = json.loads(args[1])
        self.assertEqual(enqueued_data["lane_key"], "test_lane")
        self.assertEqual(enqueued_data["data"], {"test": "data"})

    @patch('redis.asyncio.from_url')
    async def test_is_processed(self, mock_redis_from_url):
        mock_redis = AsyncMock()
        mock_redis_from_url.return_value = mock_redis
        mock_redis.sismember.return_value = True
        
        queue = RedisLaneQueue()
        res = await queue.is_processed_async("task_123")
        
        self.assertTrue(res)
        mock_redis.sismember.assert_called_with("angel_claw_lane_queue:processed", "task_123")

if __name__ == "__main__":
    unittest.main()
