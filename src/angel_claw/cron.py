import os
import json
import asyncio
import logging
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel, Field
from croniter import croniter
from .config import settings

logger = logging.getLogger("angel-claw-cron")

seconds = lambda x: timedelta(seconds=x)
minutes = lambda x: timedelta(minutes=x)
hours = lambda x: timedelta(hours=x)
days = lambda x: timedelta(days=x)


class JobSchedule(BaseModel):
    kind: str  # "at", "every", "cron", "in"
    value: str  # e.g., "2026-02-18 15:00:00", "30m", "0 9 * * *", "1h"


class JobPayload(BaseModel):
    kind: str  # "message", "prompt", "skill"
    content: Optional[str] = None
    skill_name: Optional[str] = None
    args: Optional[Dict[str, Any]] = None


class Job(BaseModel):
    name: str
    schedule: JobSchedule
    payload: JobPayload
    session_id: str = "default"
    user_id: str = "alice"
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    enabled: bool = True


class CronManager:
    def __init__(self, persist_dir: str = None):
        self.persist_dir = persist_dir or os.path.join(
            settings.memory_persist_dir, "cron"
        )
        if not os.path.exists(self.persist_dir):
            os.makedirs(self.persist_dir)
        self.jobs: Dict[str, Job] = {}
        self.load_jobs()
        self.proactive_handlers: List[Callable] = []

    def register_proactive_handler(self, handler: Callable):
        self.proactive_handlers.append(handler)

    def load_jobs(self):
        for filename in os.listdir(self.persist_dir):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(self.persist_dir, filename), "r") as f:
                        data = json.load(f)
                        job = Job(**data)
                        if job.enabled:
                            self._calculate_next_run(job)
                        self.jobs[job.name] = job
                except Exception as e:
                    logger.error(f"Error loading job {filename}: {e}")

    def save_job(self, job: Job):
        self.jobs[job.name] = job
        file_path = os.path.join(self.persist_dir, f"{job.name}.json")
        with open(file_path, "w") as f:
            f.write(job.model_dump_json(indent=2))

    def delete_job(self, name: str):
        if name in self.jobs:
            del self.jobs[name]
            file_path = os.path.join(self.persist_dir, f"{name}.json")
            if os.path.exists(file_path):
                os.remove(file_path)

    def _calculate_next_run(self, job: Job):
        now = datetime.now()
        if job.schedule.kind == "at":
            try:
                dt = datetime.fromisoformat(job.schedule.value)
                job.next_run = dt if dt > now else None
            except ValueError:
                logger.error(
                    f"Invalid 'at' schedule for job {job.name}: {job.schedule.value}"
                )
        elif job.schedule.kind in ["every", "in"]:
            value = job.schedule.value
            try:
                unit = value[-1]
                amount = int(value[:-1])
                deltas = {"s": seconds, "m": minutes, "h": hours, "d": days}
                delta = deltas[unit](amount)

                if job.schedule.kind == "in":
                    job.next_run = (now + delta) if not job.last_run else None
                    if not job.last_run:
                        job.enabled = False
                else:
                    job.next_run = (
                        (job.last_run + delta) if job.last_run else (now + delta)
                    )
            except (KeyError, ValueError):
                logger.error(
                    f"Invalid {job.schedule.kind} schedule for job {job.name}: {job.schedule.value}"
                )
        elif job.schedule.kind == "cron":
            try:
                base = job.last_run or now
                iter = croniter(job.schedule.value, base)
                job.next_run = iter.get_next(datetime)
            except Exception as e:
                logger.error(
                    f"Invalid cron expression for job {job.name}: {job.schedule.value} - {e}"
                )

    async def _execute_job(self, job: Job):
        logger.info(f"Executing job: {job.name}")
        job.last_run = datetime.now()

        try:
            if job.payload.kind == "message":
                await self._send_proactive_message(
                    job.payload.content, job.user_id, job.session_id
                )
            elif job.payload.kind == "prompt":
                from .engine import AngelClawEngine
                from .models import UserContext

                engine = AngelClawEngine()
                context = UserContext(
                    user_id=job.user_id,
                    email=f"{job.user_id}@angelclaw.local",
                    roles=["user"],
                    channel_type="cron",
                    channel_identifier=job.session_id
                )
                response = await engine.execute(context, job.payload.content)
                await self._send_proactive_message(
                    response.content, job.user_id, job.session_id
                )
            elif job.payload.kind == "skill":
                from .engine import AngelClawEngine
                from .models import UserContext
                import inspect

                engine = AngelClawEngine()
                # Skill execution logic
                if job.payload.skill_name in engine.skill_manager.skills:
                    func = engine.skill_manager.skills[job.payload.skill_name]
                    
                    args = job.payload.args or {}
                    sig = inspect.signature(func)
                    if "session_id" in sig.parameters and "session_id" not in args:
                        args["session_id"] = job.session_id
                    if "user_id" in sig.parameters and "user_id" not in args:
                        args["user_id"] = job.user_id

                    if inspect.iscoroutinefunction(func):
                        res = await func(**args)
                    else:
                        res = func(**args)

                    # Optionally notify user of result?
                    # await self._send_proactive_message(f"Skill {job.payload.skill_name} executed: {res}", job.user_id)
                else:
                    logger.error(
                        f"Skill {job.payload.skill_name} not found for job {job.name}"
                    )
        except Exception as e:
            logger.error(f"Error executing job {job.name}: {e}")

        # Recalculate next run or disable if one-shot
        if job.schedule.kind in ["at", "in"]:
            job.enabled = False
            job.next_run = None
        else:
            self._calculate_next_run(job)

        self.save_job(job)

    async def _send_proactive_message(
        self, message: str, user_id: str, session_id: str = "default"
    ):
        # Call registered handlers (e.g., Telegram, WhatsApp)
        import inspect

        for handler in self.proactive_handlers:
            try:
                if not callable(handler):
                    logger.error(f"Proactive handler {handler} is not callable!")
                    continue

                if inspect.iscoroutinefunction(handler):
                    await handler(message, user_id, session_id)
                else:
                    # Check if it returns a coroutine (some bound methods behave this way)
                    res = handler(message, user_id, session_id)
                    if inspect.isawaitable(res):
                        await res
            except Exception as e:
                logger.error(
                    f"Error in proactive handler {handler}: {e}", exc_info=True
                )

        if settings.proactive_webhook_url:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        settings.proactive_webhook_url,
                        json={
                            "user_id": user_id,
                            "session_id": session_id,
                            "message": message,
                            "source": "angel-claw-cron",
                        },
                    )
            except Exception as e:
                logger.error(f"Error sending proactive message to webhook: {e}")

        # Always log to console for CLI visibility if debug is on
        logger.info(f"PROACTIVE MESSAGE to {user_id} ({session_id}): {message}")
        if settings.debug:
            print(f"\n[PROACTIVE] {user_id} ({session_id}): {message}", flush=True)

    async def run(self):
        logger.info("Cron worker started.")
        while True:
            now = datetime.now()
            jobs_to_run = []
            for job in list(self.jobs.values()):
                if job.enabled and job.next_run and job.next_run <= now:
                    jobs_to_run.append(job)

            for job in jobs_to_run:
                await self._execute_job(job)

            await asyncio.sleep(10)  # Check every 10 seconds


cron_manager = CronManager()
