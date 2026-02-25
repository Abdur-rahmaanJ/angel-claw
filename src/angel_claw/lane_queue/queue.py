import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Dict, Set, Tuple
from .task import Task
from ..config import settings

logger = logging.getLogger("angel-claw-lane-queue")

MAX_PROCESSED_TASKS = 20000
CLEANUP_INTERVAL_SECONDS = 3600
ENQUEUE_TIMEOUT_SECONDS = 5.0
WORKER_ERROR_RETRY_DELAY = 1


class LaneQueue:
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
        logger.info(f"Starting {num_workers} lane workers...")
        for i in range(num_workers):
            worker = LaneWorker(self, worker_id=i)
            self._workers.append(asyncio.create_task(worker.run()))

    def is_processed(self, task_id: str) -> bool:
        return task_id in self._processed_ids

    def mark_processed(self, task_id: str):
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
        if self._queue.is_processed(task.task_id):
            logger.info(f"Task {task.task_id} already processed.")
            return

        async with self._queue._global_semaphore, self._semaphores[task.lane_key]:
            logger.debug(f"Worker {self._worker_id} executing Task {task.task_id}")
            try:
                await asyncio.wait_for(
                    task.execute_func(task.data),
                    timeout=settings.lane_queue_task_timeout_seconds,
                )
                self._queue.mark_processed(task.task_id)
            except asyncio.TimeoutError:
                logger.error(f"Task {task.task_id} TIMED OUT.")
            except Exception as e:
                logger.error(f"Task {task.task_id} FAILED: {e}")


lane_queue = LaneQueue()
