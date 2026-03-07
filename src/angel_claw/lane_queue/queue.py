import asyncio
import logging
import time
import json
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from typing import Dict, Set, Tuple, Optional, Any
from .task import Task
from ..config import settings

logger = logging.getLogger("angel-claw-lane-queue")

MAX_PROCESSED_TASKS = 20000
CLEANUP_INTERVAL_SECONDS = 3600
ENQUEUE_TIMEOUT_SECONDS = 5.0
WORKER_ERROR_RETRY_DELAY = 1

class BaseLaneQueue(ABC):
    @abstractmethod
    async def enqueue(self, task: Task) -> str:
        pass

    @abstractmethod
    def start_workers(self, num_workers: int = settings.lane_queue_num_workers):
        pass

    @abstractmethod
    async def is_processed_async(self, task_id: str) -> bool:
        pass

    @abstractmethod
    async def mark_processed_async(self, task_id: str):
        pass

class InMemoryLaneQueue(BaseLaneQueue):
    def __init__(self):
        self._lanes: defaultdict[str, asyncio.Queue[Task]] = defaultdict(
            lambda: asyncio.Queue(maxsize=settings.lane_queue_max_lane_depth)
        )
        self._work_available: asyncio.Queue[str] = asyncio.Queue()
        self._global_semaphore = asyncio.Semaphore(settings.lane_queue_global_max_tasks)
        self._workers: list[asyncio.Task] = []

        self._processed_tasks: deque[Tuple[str, float]] = deque(
            maxlen=MAX_PROCESSED_TASKS
        )
        self._processed_ids: Set[str] = set()
        self._processed_lock = asyncio.Lock()
        self._cleanup_interval = CLEANUP_INTERVAL_SECONDS
        self._last_cleanup = time.time()

    async def enqueue(self, task: Task) -> str:
        try:
            await asyncio.wait_for(
                self._lanes[task.lane_key].put(task), timeout=ENQUEUE_TIMEOUT_SECONDS
            )
            await self._work_available.put(task.lane_key)
            logger.debug(f"Task {task.task_id} enqueued in lane {task.lane_key}")
            return task.task_id
        except asyncio.TimeoutError:
            logger.warning(f"Backpressure: Lane {task.lane_key} is full.")
            raise Exception(f"Lane {task.lane_key} is saturated")

    def start_workers(self, num_workers: int = settings.lane_queue_num_workers):
        logger.info(f"Starting {num_workers} in-memory lane workers...")
        for i in range(num_workers):
            worker = LaneWorker(self, worker_id=i)
            self._workers.append(asyncio.create_task(worker.run()))

    async def is_processed_async(self, task_id: str) -> bool:
        async with self._processed_lock:
            return task_id in self._processed_ids

    async def mark_processed_async(self, task_id: str):
        async with self._processed_lock:
            current_time = time.time()
            if current_time - self._last_cleanup > self._cleanup_interval:
                self._cleanup_old_entries()

            if task_id not in self._processed_ids:
                self._processed_tasks.append((task_id, current_time))
                self._processed_ids.add(task_id)

    def _cleanup_old_entries(self):
        cutoff = time.time() - CLEANUP_INTERVAL_SECONDS
        new_tasks = deque(maxlen=MAX_PROCESSED_TASKS)
        new_ids = set()

        for task_id, timestamp in self._processed_tasks:
            if timestamp > cutoff:
                new_tasks.append((task_id, timestamp))
                new_ids.add(task_id)

        removed = len(self._processed_tasks) - len(new_tasks)
        self._processed_tasks = new_tasks
        self._processed_ids = new_ids
        self._last_cleanup = time.time()

        if removed > 0:
            logger.info(f"Cleaned up {removed} old processed tasks")

class RedisLaneQueue(BaseLaneQueue):
    def __init__(self):
        import redis.asyncio as redis
        self._redis = redis.from_url(settings.redis_url)
        self._queue_name = settings.redis_queue_name
        self._processed_set = f"{self._queue_name}:processed"
        self._global_semaphore = asyncio.Semaphore(settings.lane_queue_global_max_tasks)
        self._workers: list[asyncio.Task] = []
        self._semaphores: Dict[str, asyncio.Semaphore] = {}

    async def enqueue(self, task: Task) -> str:
        # Note: execute_func is not serialized. Redis queue is mainly for 
        # distributing tasks across workers. The execute_func must be 
        # re-attached or handled by the specialized worker.
        # For Angel Claw's current architecture where bridges and gateway
        # run in the same or separate processes but same codebase, 
        # we'll assume the worker knows how to execute chat requests.
        task_data = task.model_dump()
        await self._redis.lpush(self._queue_name, json.dumps(task_data))
        logger.debug(f"Task {task.task_id} enqueued in Redis lane {task.lane_key}")
        return task.task_id

    def start_workers(self, num_workers: int = settings.lane_queue_num_workers):
        logger.info(f"Starting {num_workers} Redis lane workers...")
        for i in range(num_workers):
            worker = RedisLaneWorker(self, worker_id=i)
            self._workers.append(asyncio.create_task(worker.run()))

    async def is_processed_async(self, task_id: str) -> bool:
        return await self._redis.sismember(self._processed_set, task_id)

    async def mark_processed_async(self, task_id: str):
        await self._redis.sadd(self._processed_set, task_id)
        # Optional: Set TTL for the set or items if needed

class LaneWorker:
    def __init__(self, queue: InMemoryLaneQueue, worker_id: int):
        self._queue = queue
        self._worker_id = worker_id
        self._semaphores: defaultdict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(settings.lane_queue_default_concurrency)
        )

    async def run(self):
        logger.debug(f"In-memory Worker {self._worker_id} ready.")
        while True:
            try:
                lane_key = await self._queue._work_available.get()
                task = self._queue._lanes[lane_key].get_nowait()
                await self.process_task(task)
                self._queue._lanes[lane_key].task_done()
                self._queue._work_available.task_done()
            except asyncio.QueueEmpty:
                continue
            except Exception as e:
                logger.error(f"Worker {self._worker_id} error: {e}")
                await asyncio.sleep(WORKER_ERROR_RETRY_DELAY)

    async def process_task(self, task: Task):
        if await self._queue.is_processed_async(task.task_id):
            logger.info(f"Task {task.task_id} already processed.")
            return

        async with self._queue._global_semaphore, self._semaphores[task.lane_key]:
            logger.debug(f"Worker {self._worker_id} executing Task {task.task_id}")
            try:
                if task.execute_func:
                    await asyncio.wait_for(
                        task.execute_func(task.data),
                        timeout=settings.lane_queue_task_timeout_seconds,
                    )
                await self._queue.mark_processed_async(task.task_id)
            except asyncio.TimeoutError:
                logger.error(f"Task {task.task_id} TIMED OUT.")
            except Exception as e:
                logger.error(f"Task {task.task_id} FAILED: {e}")

class RedisLaneWorker:
    def __init__(self, queue: RedisLaneQueue, worker_id: int):
        self._queue = queue
        self._worker_id = worker_id
        self._semaphores: Dict[str, asyncio.Semaphore] = {}

    async def run(self):
        logger.debug(f"Redis Worker {self._worker_id} ready.")
        while True:
            try:
                # BRPOP blocks until a task is available
                _, task_json = await self._queue._redis.brpop(self._queue._queue_name)
                task_data = json.loads(task_json)
                task = Task(**task_data)
                
                # Re-attach the execute_func for chat requests
                # This is a bit of a hack but necessary for Redis-based task distribution
                # in the current architecture.
                if "message" in task.data and "session_id" in task.data:
                    from .process import agent_chat_wrapper, _results_lock, results, _events_lock, events
                    
                    async def execute_and_set_result(t_data: Any):
                        try:
                            # We need to handle the case where the requester might be on a different node
                            # For a true distributed system, results would also go through Redis (Pub/Sub)
                            result = await agent_chat_wrapper(t_data["request"], t_data["context"])
                            async with _results_lock:
                                results[task.task_id] = result
                        except Exception as e:
                            logger.error(f"Error executing Redis task {task.task_id}: {e}")
                        finally:
                            async with _events_lock:
                                if task.task_id in events:
                                    events[task.task_id].set()

                    task.execute_func = execute_and_set_result

                await self.process_task(task)
            except Exception as e:
                logger.error(f"Redis Worker {self._worker_id} error: {e}")
                await asyncio.sleep(WORKER_ERROR_RETRY_DELAY)

    async def process_task(self, task: Task):
        if await self._queue.is_processed_async(task.task_id):
            return

        lane_key = task.lane_key
        if lane_key not in self._semaphores:
            self._semaphores[lane_key] = asyncio.Semaphore(settings.lane_queue_default_concurrency)
        
        async with self._queue._global_semaphore, self._semaphores[lane_key]:
            try:
                if task.execute_func:
                    await asyncio.wait_for(
                        task.execute_func(task.data),
                        timeout=settings.lane_queue_task_timeout_seconds,
                    )
                await self._queue.mark_processed_async(task.task_id)
            except Exception as e:
                logger.error(f"Redis Task {task.task_id} FAILED: {e}")

# Global instance factory
def get_lane_queue() -> BaseLaneQueue:
    if settings.redis_enabled:
        try:
            return RedisLaneQueue()
        except ImportError:
            logger.error("Redis enabled but 'redis' package not installed. Falling back to in-memory.")
            return InMemoryLaneQueue()
    return InMemoryLaneQueue()

lane_queue = get_lane_queue()
