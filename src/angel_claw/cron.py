import os
import json
import time
import asyncio
import logging
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.base import BaseTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from .config import settings

logger = logging.getLogger("angel-claw-cron")

# How often the worker re-reads the shared job directory to pick up jobs
# created by another process (web app, CLI).
JOB_RELOAD_INTERVAL_SECONDS = 15

# Only one process may execute jobs from a given directory (otherwise `serve`
# and `bridges` would each fire every reminder). The owner heartbeat-touches
# this file; a worker that dies leaves a lease that expires after the TTL.
WORKER_LEASE_FILE = ".cron_worker.lock"
WORKER_LEASE_TTL_SECONDS = 3 * JOB_RELOAD_INTERVAL_SECONDS

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
    user_id: str = "cli"
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
        self._jobs_lock = asyncio.Lock()
        # Modification times of the job files this manager last read or wrote.
        # Used to notice jobs another process (e.g. the web app) created.
        self._job_mtimes: Dict[str, float] = {}
        # Scheduling engine: APScheduler replaces the hand-rolled poll loop.
        # Created here, started later inside run() (needs a running loop).
        self.scheduler = AsyncIOScheduler()
        # One-shot jobs dropped as stale while loading; reported by run().
        self.missed_jobs: List[Job] = []
        self.load_jobs()
        self.proactive_handlers: List[Callable] = []

    def register_proactive_handler(self, handler: Callable):
        self.proactive_handlers.append(handler)

    def load_jobs(self):
        for filename in os.listdir(self.persist_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.persist_dir, filename)
                try:
                    with open(path, "r") as f:
                        data = json.load(f)
                        job = Job(**data)
                        if job.enabled:
                            self._calculate_next_run(job)
                        self.jobs[job.name] = job
                        # mtimes are keyed by filename: a hand-written job file
                        # may not match its inner name.
                        self._job_mtimes[filename[: -len(".json")]] = (
                            os.path.getmtime(path)
                        )
                except Exception as e:
                    logger.error(f"Error loading job {filename}: {e}")

    def _write_job_file(self, job: Job):
        path = os.path.join(self.persist_dir, f"{job.name}.json")
        tmp_path = f"{path}.tmp"
        # Atomic replace: a reader in another process must never see a
        # half-written file.
        with open(tmp_path, "w") as f:
            f.write(job.model_dump_json(indent=2))
        os.replace(tmp_path, path)
        try:
            self._job_mtimes[job.name] = os.path.getmtime(path)
        except OSError:
            pass

    async def save_job_async(self, job: Job):
        # Always compute next_run before persisting, otherwise one-shot "at"
        # jobs created at runtime never enter the execution loop. Never clobber
        # a schedule the caller already set (e.g. a job forced to run now).
        if job.next_run is None:
            self._calculate_next_run(job)
        async with self._jobs_lock:
            self.jobs[job.name] = job
        self._write_job_file(job)
        self._sync_job(job)

    def save_job(self, job: Job):
        # See save_job_async: respect an explicit next_run, else compute it.
        if job.next_run is None:
            self._calculate_next_run(job)
        self.jobs[job.name] = job
        self._write_job_file(job)
        self._sync_job(job)

    async def delete_job_async(self, name: str):
        async with self._jobs_lock:
            if name in self.jobs:
                del self.jobs[name]
        file_path = os.path.join(self.persist_dir, f"{name}.json")
        if os.path.exists(file_path):
            os.remove(file_path)
        self._job_mtimes.pop(name, None)
        self._unschedule(name)

    def delete_job(self, name: str):
        if name in self.jobs:
            del self.jobs[name]
        file_path = os.path.join(self.persist_dir, f"{name}.json")
        if os.path.exists(file_path):
            os.remove(file_path)
        self._job_mtimes.pop(name, None)
        self._unschedule(name)

    def reload_jobs_from_disk(self):
        """Adopt jobs created, changed or deleted by another process.

        The persist directory is shared with the web app (and the CLI), so a
        reminder set in the UI lands in a JSON file that the cron worker never
        loaded. Polling the file mtimes makes those jobs visible without
        restarting the worker, and equally drops jobs deleted elsewhere.
        """
        if not os.path.isdir(self.persist_dir):
            return

        seen = set()
        for filename in os.listdir(self.persist_dir):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(self.persist_dir, filename)
            name = filename[: -len(".json")]
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            # A file we cannot parse yet (mid-write) is still present: mark it
            # seen so a transient read error does not delete the live job.
            seen.add(name)
            if self._job_mtimes.get(name) == mtime:
                continue
            try:
                with open(path, "r") as f:
                    job = Job(**json.load(f))
            except Exception as e:
                logger.debug(f"Could not reload job {filename} yet: {e}")
                continue
            self._job_mtimes[name] = mtime
            seen.add(job.name)
            if job.enabled:
                self._calculate_next_run(job)
            self.jobs[job.name] = job
            self._sync_job(job)
            logger.info(f"Picked up job {job.name} from disk")

        for name in list(self.jobs):
            if name in seen:
                continue
            logger.info(f"Dropping job {name}: no longer on disk")
            del self.jobs[name]
            self._job_mtimes.pop(name, None)
            self._unschedule(name)

    @property
    def _lease_path(self) -> str:
        return os.path.join(self.persist_dir, WORKER_LEASE_FILE)

    def _acquire_lease(self) -> bool:
        """Become the only worker allowed to execute jobs in this directory."""
        path = self._lease_path
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            try:
                age = time.time() - os.path.getmtime(path)
            except OSError:
                return False
            if age <= WORKER_LEASE_TTL_SECONDS:
                return False
            logger.warning("Taking over stale cron worker lease")
            try:
                os.remove(path)
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except OSError:
                return False
        with os.fdopen(fd, "w") as f:
            f.write(str(os.getpid()))
        return True

    def _renew_lease(self) -> bool:
        try:
            with open(self._lease_path, "r") as f:
                if f.read().strip() != str(os.getpid()):
                    return False
            os.utime(self._lease_path, None)
            return True
        except OSError:
            return False

    def _release_lease(self):
        try:
            with open(self._lease_path, "r") as f:
                if f.read().strip() != str(os.getpid()):
                    return
            os.remove(self._lease_path)
        except OSError:
            pass

    async def _notify_missed_jobs(self):
        """Tell the user about one-shot jobs skipped as too old."""
        missed = list(self.missed_jobs)
        self.missed_jobs.clear()
        for job in missed:
            content = job.payload.content or job.payload.skill_name or job.name
            message = f"⚠️ Missed task: {content} (was due {job.schedule.value})"
            if job.name.startswith("reminder_"):
                try:
                    from angel_claw.engine.app_context import (
                        create_app_context_manager,
                    )
                    from angel_claw.config import settings

                    ctx_manager = create_app_context_manager(settings)
                    with ctx_manager._app_context() as app:
                        if app is not None:
                            from modules.agent.models import InternalMessage
                            from shopyo_auth.models import User
                            from init import db

                            user_key = (
                                int(job.user_id)
                                if str(job.user_id).isdigit()
                                else job.user_id
                            )
                            user = db.session.get(User, user_key)
                            if user:
                                db.session.add(
                                    InternalMessage(
                                        sender_id="system",
                                        recipient_id=str(user.id),
                                        recipient_email=user.email,
                                        content=message,
                                    )
                                )
                                db.session.commit()
                except Exception as e:
                    logger.error(f"Error storing missed-task notice: {e}")
            await self._send_proactive_message(
                message, job.user_id, job.session_id
            )

    async def _reload_loop(self):
        while True:
            await asyncio.sleep(JOB_RELOAD_INTERVAL_SECONDS)
            try:
                self.reload_jobs_from_disk()
            except Exception as e:
                logger.error(f"Error reloading cron jobs from disk: {e}")
            if not self._renew_lease():
                logger.error("Lost the cron worker lease; another worker owns it")
                return

    # --- APScheduler wiring -------------------------------------------

    @staticmethod
    def _parse_delta(value: str) -> timedelta:
        unit = value[-1]
        amount = int(value[:-1])
        return {"s": seconds, "m": minutes, "h": hours, "d": days}[unit](amount)

    @staticmethod
    def _naive(dt: Optional[datetime]) -> Optional[datetime]:
        # Triggers return tz-aware datetimes; jobs, files and the rest of the
        # codebase use naive local time.
        if dt is not None and dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt

    def _build_trigger(self, job: Job) -> BaseTrigger:
        """Map a JobSchedule onto an APScheduler trigger."""
        kind, value = job.schedule.kind, job.schedule.value
        if kind == "at":
            # next_run wins: it may be "now" for a late one-shot job
            return DateTrigger(run_date=job.next_run or datetime.fromisoformat(value))
        if kind == "in":
            return DateTrigger(
                run_date=job.next_run or datetime.now() + self._parse_delta(value)
            )
        if kind == "cron":
            return CronTrigger.from_crontab(value)
        if kind == "every":
            delta = self._parse_delta(value)
            start = job.last_run + delta if job.last_run else datetime.now() + delta
            return IntervalTrigger(seconds=delta.total_seconds(), start_date=start)
        raise ValueError(f"unknown schedule kind: {kind}")

    def _calculate_next_run(self, job: Job):
        now = datetime.now()
        kind = job.schedule.kind
        value = job.schedule.value
        try:
            if kind == "at":
                dt = datetime.fromisoformat(value)
                if dt > now:
                    job.next_run = dt
                elif job.last_run is None and job.enabled:
                    # One-shot job whose time already passed but never ran
                    # (saved late or server restarted): fire it now unless it
                    # is stale (older than 24h) — then just disable it.
                    if now - dt < timedelta(days=1):
                        job.next_run = now
                    else:
                        job.next_run = None
                        job.enabled = False
                        self.missed_jobs.append(job)
                        logger.warning(
                            f"Disabling stale one-shot job {job.name} scheduled for {dt}"
                        )
                else:
                    job.next_run = None
                return
            if kind == "in":
                if job.last_run:
                    # one-shot "in" job that already fired: nothing left to do
                    job.next_run = None
                    job.enabled = False
                    return
                job.enabled = True
            # APScheduler triggers expect a tz-aware "now"
            job.next_run = self._naive(
                self._build_trigger(job).get_next_fire_time(
                    None, datetime.now().astimezone()
                )
            )
        except Exception as e:
            logger.error(
                f"Invalid {kind} schedule for job {job.name}: {value} - {e}"
            )

    def _sync_job(self, job: Job):
        """Add or refresh one job inside the scheduler."""
        self._unschedule(job.name)
        if not job.enabled or not job.next_run:
            return
        try:
            trigger = self._build_trigger(job)
        except Exception as e:
            logger.error(f"Cannot schedule job {job.name}: {e}")
            return
        self.scheduler.add_job(
            self._run_job,
            trigger=trigger,
            args=[job.name],
            id=job.name,
            replace_existing=True,
            coalesce=True,
            # Run overdue jobs instead of dropping them: APScheduler's default
            # grace period is 1s, which loses jobs on a busy event loop.
            misfire_grace_time=None,
            max_instances=1,
        )

    def _unschedule(self, name: str):
        try:
            self.scheduler.remove_job(name)
        except Exception:
            pass  # not scheduled yet, or scheduler not running

    def _schedule_all_jobs(self):
        for job in list(self.jobs.values()):
            self._sync_job(job)

    async def _run_job(self, job_name: str):
        job = self.jobs.get(job_name)
        if job is None or not job.enabled:
            self._unschedule(job_name)
            return
        await self._execute_job(job)

    async def _execute_job(self, job: Job):
        logger.info(f"Executing job: {job.name}")
        job.last_run = datetime.now()

        # Handle Reminders persistence
        if job.name.startswith("reminder_"):
            try:
                # Use the shared app-context helper (falls back to creating a
                # Flask app when running outside a request, e.g. cron thread).
                from angel_claw.engine.app_context import create_app_context_manager
                from angel_claw.config import settings

                ctx_manager = create_app_context_manager(settings)
                with ctx_manager._app_context() as app:
                    if app is None:
                        raise RuntimeError("No Flask app context available")
                    from modules.agent.models import Reminder, InternalMessage
                    from init import db
                    reminder = Reminder.query.filter_by(job_name=job.name).first()
                    if reminder:
                        reminder.is_sent = True

                        # For web reminders, also create an InternalMessage for the UI to pick up
                        if reminder.channel_type == "web":
                            from shopyo_auth.models import User
                            # Handle numeric ID string for User lookup
                            user_id_val = int(reminder.user_id) if reminder.user_id.isdigit() else reminder.user_id
                            user = db.session.get(User, user_id_val)
                            if user:
                                msg = InternalMessage(
                                    sender_id="system",
                                    recipient_id=str(user.id),
                                    recipient_email=user.email,
                                    content=f"🔔 REMINDER: {reminder.message}"
                                )
                                db.session.add(msg)
                            else:
                                logger.error(f"User not found for reminder: {reminder.user_id}")

                        db.session.commit()
            except Exception as e:
                logger.error(f"Error updating reminder status: {e}", exc_info=True)

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
                    channel_identifier=job.session_id,
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

        await self.save_job_async(job)

    async def _send_proactive_message(
        self, message: str, user_id: str, session_id: str = "default"
    ):
        # Normalize session_id: if it looks like an email from our bridges, extract the ID
        # e.g. "telegram_8694052043@angelclaw.local" -> "8694052043"
        clean_sid = session_id
        if "@" in session_id:
            user_part = session_id.split("@")[0]
            if "_" in user_part:
                clean_sid = user_part.split("_")[-1]

        # Call registered handlers (e.g., Telegram, WhatsApp)
        import inspect

        for handler in self.proactive_handlers:
            try:
                if not callable(handler):
                    logger.error(f"Proactive handler {handler} is not callable!")
                    continue

                if inspect.iscoroutinefunction(handler):
                    await handler(message, user_id, clean_sid)
                else:
                    # Check if it returns a coroutine (some bound methods behave this way)
                    res = handler(message, user_id, clean_sid)
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
                            "session_id": clean_sid,
                            "message": message,
                            "source": "angel-claw-cron",
                        },
                    )
            except Exception as e:
                logger.error(f"Error sending proactive message to webhook: {e}")

        # Always log to console for CLI visibility if debug is on
        logger.info(f"PROACTIVE MESSAGE to {user_id} ({clean_sid}): {message}")
        if settings.debug:
            print(f"\n[PROACTIVE] {user_id} ({clean_sid}): {message}", flush=True)

    async def run(self):
        """Start APScheduler and block until this task is cancelled."""
        if self.scheduler.running:
            # another run() call already owns the scheduler
            await asyncio.Event().wait()
            return

        while not self._acquire_lease():
            logger.info(
                "Another cron worker owns this job directory; waiting for the lease."
            )
            await asyncio.sleep(JOB_RELOAD_INTERVAL_SECONDS)

        logger.info("Cron worker started (APScheduler).")
        reload_task = None
        try:
            self.scheduler.start()  # flushes jobs queued before start
            # Jobs loaded from disk were never added to the scheduler; without
            # this they would sit enabled in the JSON files and never fire.
            self._schedule_all_jobs()
            if self.missed_jobs:
                await self._notify_missed_jobs()
            # Keep watching the shared directory for jobs another process adds.
            reload_task = asyncio.create_task(self._reload_loop())
            await asyncio.Event().wait()
        finally:
            if reload_task is not None:
                reload_task.cancel()
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
            self._release_lease()


cron_manager = CronManager()
