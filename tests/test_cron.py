import pytest
import os
import shutil
import asyncio
import json
from datetime import datetime, timedelta
from angel_claw.cron import CronManager, Job, JobSchedule, JobPayload
from angel_claw.config import settings

@pytest.fixture
def test_cron_dir():
    test_dir = "./test_cron_vaults"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir)
    yield test_dir
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

def test_cron_manager_save_load(test_cron_dir):
    manager = CronManager(persist_dir=test_cron_dir)
    job = Job(
        name="test_job",
        schedule=JobSchedule(kind="at", value="2030-01-01 12:00:00"),
        payload=JobPayload(kind="message", content="Hello")
    )
    manager.save_job(job)
    
    # New manager instance to test loading
    manager2 = CronManager(persist_dir=test_cron_dir)
    assert "test_job" in manager2.jobs
    assert manager2.jobs["test_job"].payload.content == "Hello"

def test_cron_calculation():
    manager = CronManager(persist_dir="./test_tmp_cron")
    
    # Test 'at'
    job_at = Job(
        name="at_job",
        schedule=JobSchedule(kind="at", value="2030-01-01 12:00:00"),
        payload=JobPayload(kind="message", content="At")
    )
    manager._calculate_next_run(job_at)
    assert job_at.next_run == datetime.fromisoformat("2030-01-01 12:00:00")
    
    # Test 'every'
    job_every = Job(
        name="every_job",
        schedule=JobSchedule(kind="every", value="30m"),
        payload=JobPayload(kind="message", content="Every")
    )
    manager._calculate_next_run(job_every)
    # last_run is None, so it should be now + 30m
    now = datetime.now()
    assert job_every.next_run > now + timedelta(minutes=29)
    assert job_every.next_run < now + timedelta(minutes=31)
    
    # Test 'cron'
    job_cron = Job(
        name="cron_job",
        schedule=JobSchedule(kind="cron", value="0 9 * * *"),
        payload=JobPayload(kind="message", content="Cron")
    )
    manager._calculate_next_run(job_cron)
    assert job_cron.next_run.hour == 9
    assert job_cron.next_run.minute == 0

    if os.path.exists("./test_tmp_cron"):
        shutil.rmtree("./test_tmp_cron")

@pytest.mark.asyncio
async def test_cron_execution_trigger(test_cron_dir, monkeypatch):
    manager = CronManager(persist_dir=test_cron_dir)
    
    executed = False
    async def mock_send(message, user_id, session_id="default"):
        nonlocal executed
        executed = True
    
    monkeypatch.setattr(manager, "_send_proactive_message", mock_send)
    
    # Job scheduled for now
    now = datetime.now()
    job = Job(
        name="immediate_job",
        schedule=JobSchedule(kind="at", value=(now + timedelta(hours=1)).isoformat()),
        payload=JobPayload(kind="message", content="Now"),
        enabled=True
    )
    # Manually force it to be due
    job.next_run = now - timedelta(seconds=1)
    manager.save_job(job)
    
    # Run once
    jobs_to_run = []
    for j in list(manager.jobs.values()):
        if j.enabled and j.next_run and j.next_run <= datetime.now():
            jobs_to_run.append(j)
    
    for j in jobs_to_run:
        await manager._execute_job(j)
        
    assert executed
    assert job.enabled == False # 'at' jobs should be disabled after run


@pytest.mark.asyncio
async def test_scheduler_fires_one_shot_job(test_cron_dir, monkeypatch):
    """The APScheduler-backed run() must actually execute a due job."""
    manager = CronManager(persist_dir=test_cron_dir)

    fired = asyncio.Event()

    async def mock_send(message, user_id, session_id="default"):
        fired.set()

    monkeypatch.setattr(manager, "_send_proactive_message", mock_send)

    job = Job(
        name="oneshot_job",
        schedule=JobSchedule(kind="in", value="1s"),
        payload=JobPayload(kind="message", content="soon"),
        enabled=True,
    )
    manager.save_job(job)

    task = asyncio.create_task(manager.run())
    try:
        await asyncio.wait_for(fired.wait(), timeout=10)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert manager.jobs["oneshot_job"].enabled is False
    assert manager.jobs["oneshot_job"].next_run is None


@pytest.mark.asyncio
async def test_scheduler_fires_recurring_job(test_cron_dir, monkeypatch):
    """A repeating 'every' job must fire more than once."""
    manager = CronManager(persist_dir=test_cron_dir)

    count = 0

    async def mock_send(message, user_id, session_id="default"):
        nonlocal count
        count += 1

    monkeypatch.setattr(manager, "_send_proactive_message", mock_send)

    job = Job(
        name="tick_job",
        schedule=JobSchedule(kind="every", value="1s"),
        payload=JobPayload(kind="message", content="tick"),
        enabled=True,
    )
    manager.save_job(job)

    task = asyncio.create_task(manager.run())
    try:
        deadline = asyncio.get_event_loop().time() + 15
        while count < 2 and asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(0.1)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert count >= 2, f"expected recurring job to fire twice, fired {count} times"
    assert manager.jobs["tick_job"].next_run is not None
    assert manager.jobs["tick_job"].next_run > datetime.now()


@pytest.mark.asyncio
async def test_scheduler_schedules_jobs_loaded_from_disk(test_cron_dir, monkeypatch):
    """Jobs present on disk when the worker starts must be scheduled."""
    writer = CronManager(persist_dir=test_cron_dir)
    writer.save_job(
        Job(
            name="persisted_job",
            schedule=JobSchedule(kind="in", value="1s"),
            payload=JobPayload(kind="message", content="loaded"),
            enabled=True,
        )
    )

    # Fresh instance stands in for the worker after a restart.
    manager = CronManager(persist_dir=test_cron_dir)
    fired = asyncio.Event()

    async def mock_send(message, user_id, session_id="default"):
        fired.set()

    monkeypatch.setattr(manager, "_send_proactive_message", mock_send)

    task = asyncio.create_task(manager.run())
    try:
        await asyncio.wait_for(fired.wait(), timeout=10)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert manager.jobs["persisted_job"].last_run is not None


@pytest.mark.asyncio
async def test_reload_picks_up_job_created_by_another_process(test_cron_dir, monkeypatch):
    """A reminder written by the web app must reach a running worker."""
    worker = CronManager(persist_dir=test_cron_dir)
    web = CronManager(persist_dir=test_cron_dir)
    fired = asyncio.Event()

    async def mock_send(message, user_id, session_id="default"):
        fired.set()

    monkeypatch.setattr(worker, "_send_proactive_message", mock_send)

    task = asyncio.create_task(worker.run())
    try:
        web.save_job(
            Job(
                name="from_web",
                schedule=JobSchedule(kind="in", value="1s"),
                payload=JobPayload(kind="message", content="from web"),
                enabled=True,
            )
        )
        # The periodic loop polls every 15s; poll once by hand for the test.
        worker.reload_jobs_from_disk()
        assert "from_web" in worker.jobs
        await asyncio.wait_for(fired.wait(), timeout=10)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert worker.jobs["from_web"].last_run is not None


@pytest.mark.asyncio
async def test_reload_drops_job_deleted_by_another_process(test_cron_dir):
    worker = CronManager(persist_dir=test_cron_dir)
    web = CronManager(persist_dir=test_cron_dir)

    web.save_job(
        Job(
            name="gone_job",
            schedule=JobSchedule(kind="at", value="2030-01-01T12:00:00"),
            payload=JobPayload(kind="message", content="later"),
            enabled=True,
        )
    )
    worker.reload_jobs_from_disk()
    assert "gone_job" in worker.jobs

    web.delete_job("gone_job")
    worker.reload_jobs_from_disk()
    assert "gone_job" not in worker.jobs


def test_only_one_worker_holds_the_execution_lease(test_cron_dir):
    """Two cron owners on one directory must not both execute jobs."""
    first = CronManager(persist_dir=test_cron_dir)
    second = CronManager(persist_dir=test_cron_dir)

    assert first._acquire_lease() is True
    assert second._acquire_lease() is False

    first._release_lease()
    assert second._acquire_lease() is True
    second._release_lease()


def test_stale_worker_lease_is_taken_over(test_cron_dir):
    manager = CronManager(persist_dir=test_cron_dir)
    path = manager._lease_path

    # Lease left behind by a worker that died long ago.
    with open(path, "w") as f:
        f.write("99999")
    old = datetime.now().timestamp() - 3600
    os.utime(path, (old, old))

    assert manager._acquire_lease() is True
    manager._release_lease()
