import asyncio
import logging
from collections import defaultdict
from typing import Dict, Set
from .task import Task
from ..config import settings

logger = logging.getLogger("angel-claw-lane-queue")

class LaneQueue:
    def __init__(self):
        # Per-lane queues
        self._lanes: defaultdict[str, asyncio.Queue[Task]] = defaultdict(
            lambda: asyncio.Queue(maxsize=settings.lane_queue_max_lane_depth)
        )
        # Notification queue for workers: contains lane_keys that have work
        self._work_available: asyncio.Queue[str] = asyncio.Queue()
        self._global_semaphore = asyncio.Semaphore(settings.lane_queue_global_max_tasks)
        self._workers: list[asyncio.Task] = []
        
        # In-memory idempotency set (simulating DynamoDB table)
        # In a real distributed system, this would be a TTL-enabled cache (Redis/DynamoDB)
        self._processed_tasks: Set[str] = set()

    async def enqueue(self, task: Task) -> str:
        """
        Enqueues a task into its specific lane.
        Implements backpressure by respecting the maxsize of the lane queue.
        """
        try:
            # We use wait_for to avoid blocking indefinitely if a lane is full
            # This allows the gateway to return a 503/429 instead of hanging
            await asyncio.wait_for(
                self._lanes[task.lane_key].put(task),
                timeout=5.0 
            )
            await self._work_available.put(task.lane_key)
            logger.debug(f"Task {task.task_id} enqueued in lane {task.lane_key}")
            return task.task_id
        except asyncio.TimeoutError:
            logger.warning(f"Backpressure: Lane {task.lane_key} is full. Dropping task.")
            raise Exception(f"Lane {task.lane_key} is saturated (backpressure)")

    def start_workers(self, num_workers: int = settings.lane_queue_num_workers):
        logger.info(f"Starting {num_workers} lane workers...")
        for i in range(num_workers):
            worker = LaneWorker(self, worker_id=i)
            self._workers.append(asyncio.create_task(worker.run()))

    def is_processed(self, task_id: str) -> bool:
        return task_id in self._processed_tasks

    def mark_processed(self, task_id: str):
        self._processed_tasks.add(task_id)
        # Keep the set from growing indefinitely (naive cleanup)
        if len(self._processed_tasks) > 10000:
            self._processed_tasks.clear() 

class LaneWorker:
    def __init__(self, queue: LaneQueue, worker_id: int):
        self._queue = queue
        self._worker_id = worker_id
        self._semaphores: defaultdict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(settings.lane_queue_default_concurrency)
        )

    async def run(self):
        logger.debug(f"Worker {self._worker_id} ready.")
        while True:
            try:
                # Wait for a notification that some lane has work
                lane_key = await self._queue._work_available.get()
                
                # Pull the task from that lane
                # We use get_nowait because we were notified there is work
                task = self._queue._lanes[lane_key].get_nowait()
                
                # Process it
                await self.process_task(task)
                
                # Mark as done in the asyncio queue
                self._queue._lanes[lane_key].task_done()
                self._queue._work_available.task_done()
            except asyncio.QueueEmpty:
                continue
            except Exception as e:
                logger.error(f"Worker {self._worker_id} unexpected error: {e}")
                await asyncio.sleep(1)

    async def process_task(self, task: Task):
        # 1. Idempotency Check
        if self._queue.is_processed(task.task_id):
            logger.info(f"Task {task.task_id} already processed. Skipping.")
            return

        # 2. Concurrency Control (Global & Per-Lane)
        async with self._queue._global_semaphore, self._semaphores[task.lane_key]:
            logger.debug(f"Worker {self._worker_id} executing Task {task.task_id} in lane {task.lane_key}")
            try:
                # 3. Execution with Timeout
                await asyncio.wait_for(
                    task.execute_func(task.data),
                    timeout=settings.lane_queue_task_timeout_seconds,
                )
                # 4. Success - Mark as processed
                self._queue.mark_processed(task.task_id)
            except asyncio.TimeoutError:
                logger.error(f"Task {task.task_id} in lane {task.lane_key} TIMED OUT.")
            except Exception as e:
                logger.error(f"Task {task.task_id} in lane {task.lane_key} FAILED: {e}", exc_info=True)

lane_queue = LaneQueue()
