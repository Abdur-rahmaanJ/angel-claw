import logging
import asyncio
from typing import Dict, Optional
from datetime import datetime, UTC, timedelta

from ..models import UserContext
from .user_runtime import UserRuntime

logger = logging.getLogger("angel-claw-runtime-manager")

class RuntimeManager:
    """Manages UserRuntime instances with LRU eviction."""
    def __init__(self, max_idle_minutes: int = 30, cleanup_interval_seconds: int = 60):
        self._runtimes: Dict[str, UserRuntime] = {}
        self._max_idle = timedelta(minutes=max_idle_minutes)
        self._cleanup_interval = cleanup_interval_seconds
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    async def get_runtime(self, context: UserContext) -> UserRuntime:
        """Get or create a UserRuntime for the given context."""
        async with self._lock:
            user_id = context.user_id
            if user_id not in self._runtimes:
                logger.info(f"Creating new UserRuntime for user: {user_id}")
                runtime = UserRuntime(context)
                self._runtimes[user_id] = runtime
            else:
                runtime = self._runtimes[user_id]
            
            runtime.mark_active()
            return runtime

    async def start_cleanup_task(self):
        """Start the background task for cleaning up idle runtimes."""
        if self._cleanup_task:
            return
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("RuntimeManager cleanup task started.")

    async def stop_cleanup_task(self):
        """Stop the background task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("RuntimeManager cleanup task stopped.")

    async def _cleanup_loop(self):
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self.cleanup_idle_runtimes()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in RuntimeManager cleanup loop: {e}")

    async def cleanup_idle_runtimes(self):
        """Evict runtimes that have been idle for too long."""
        now = datetime.now(UTC)
        to_evict = []
        
        async with self._lock:
            for user_id, runtime in self._runtimes.items():
                if now - runtime.last_active > self._max_idle:
                    to_evict.append(user_id)
            
            for user_id in to_evict:
                logger.info(f"Evicting idle UserRuntime for user: {user_id}")
                del self._runtimes[user_id]

# Global instance
runtime_manager = RuntimeManager()
