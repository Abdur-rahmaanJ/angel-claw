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
    async def mock_send(message, user_id):
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
