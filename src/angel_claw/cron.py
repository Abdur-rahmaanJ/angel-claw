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
        self.persist_dir = persist_dir or os.path.join(settings.memory_persist_dir, "cron")
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
                if dt > now:
                    job.next_run = dt
                else:
                    job.next_run = None
            except ValueError:
                logger.error(f"Invalid 'at' schedule for job {job.name}: {job.schedule.value}")
        elif job.schedule.kind in ["every", "in"]:
            # e.g., "30s", "1m", "1h", "1d"
            value = job.schedule.value
            try:
                if value.endswith("s"):
                    delta = timedelta(seconds=int(value[:-1]))
                elif value.endswith("m"):
                    delta = timedelta(minutes=int(value[:-1]))
                elif value.endswith("h"):
                    delta = timedelta(hours=int(value[:-1]))
                elif value.endswith("d"):
                    delta = timedelta(days=int(value[:-1]))
                else:
                    raise ValueError("Unknown unit")
                
                if job.schedule.kind == "in":
                     # One-shot relative to creation if not run, else none
                     if not job.last_run:
                         # We use job.next_run if it was already set, otherwise now + delta
                         if not job.next_run:
                             job.next_run = now + delta
                     else:
                         job.next_run = None
                         job.enabled = False
                else:
                    # Recurring
                    if job.last_run:
                        job.next_run = job.last_run + delta
                    else:
                        job.next_run = now + delta
            except ValueError:
                logger.error(f"Invalid {job.schedule.kind} schedule for job {job.name}: {job.schedule.value}")
        elif job.schedule.kind == "cron":
            try:
                base = job.last_run or now
                iter = croniter(job.schedule.value, base)
                job.next_run = iter.get_next(datetime)
            except Exception as e:
                logger.error(f"Invalid cron expression for job {job.name}: {job.schedule.value} - {e}")

    async def _execute_job(self, job: Job):
        logger.info(f"Executing job: {job.name}")
        job.last_run = datetime.now()
        
        try:
            if job.payload.kind == "message":
                await self._send_proactive_message(job.payload.content, job.user_id, job.session_id)
            elif job.payload.kind == "prompt":
                from .agent import Agent
                agent = Agent(job.session_id)
                response = await agent.chat(job.payload.content)
                await self._send_proactive_message(response, job.user_id, job.session_id)
            elif job.payload.kind == "skill":
                from .agent import Agent
                agent = Agent(job.session_id)
                # Skill execution logic
                if job.payload.skill_name in agent.skill_manager.skills:
                    func = agent.skill_manager.skills[job.payload.skill_name]
                    import inspect
                    if inspect.iscoroutinefunction(func):
                        res = await func(**(job.payload.args or {}))
                    else:
                        res = func(**(job.payload.args or {}))
                    # Optionally notify user of result?
                    # await self._send_proactive_message(f"Skill {job.payload.skill_name} executed: {res}", job.user_id)
                else:
                    logger.error(f"Skill {job.payload.skill_name} not found for job {job.name}")
        except Exception as e:
            logger.error(f"Error executing job {job.name}: {e}")
        
        # Recalculate next run or disable if one-shot
        if job.schedule.kind in ["at", "in"]:
            job.enabled = False
            job.next_run = None
        else:
            self._calculate_next_run(job)
        
        self.save_job(job)

    async def _send_proactive_message(self, message: str, user_id: str, session_id: str = "default"):
        # Call registered handlers (e.g., Telegram)
        for handler in self.proactive_handlers:
            try:
                await handler(message, user_id, session_id)
            except Exception as e:
                logger.error(f"Error in proactive handler: {e}")

        if settings.proactive_webhook_url:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(settings.proactive_webhook_url, json={
                        "user_id": user_id,
                        "session_id": session_id,
                        "message": message,
                        "source": "angel-claw-cron"
                    })
            except Exception as e:
                logger.error(f"Error sending proactive message to webhook: {e}")
        
        # Always log to console for CLI visibility if debug is on
        logger.info(f"PROACTIVE MESSAGE to {user_id} ({session_id}): {message}")
        if settings.debug:
            print(f"\n[PROACTIVE] {user_id} ({session_id}): {message}\nYou: ", end="", flush=True)

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
            
            await asyncio.sleep(10) # Check every 10 seconds

cron_manager = CronManager()
