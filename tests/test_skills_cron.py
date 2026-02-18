import pytest
import os
import shutil
from angel_claw.skills.core import schedule_task, list_tasks, delete_task
from angel_claw.cron import cron_manager

@pytest.fixture(autouse=True)
def setup_cron_test():
    test_dir = "./test_skills_cron_vaults"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir)
    # Monkeypatch manager's persist_dir
    old_dir = cron_manager.persist_dir
    cron_manager.persist_dir = test_dir
    cron_manager.jobs = {}
    yield
    cron_manager.persist_dir = old_dir
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

def test_schedule_task_skill():
    res = schedule_task(
        name="test_skill_job",
        schedule_kind="at",
        schedule_value="2030-01-01 12:00:00",
        payload_kind="message",
        content="Hello from skill"
    )
    assert "scheduled" in res
    assert "test_skill_job" in cron_manager.jobs
    
    list_res = list_tasks()
    assert "test_skill_job" in list_res
    
    del_res = delete_task("test_skill_job")
    assert "deleted" in del_res
    assert "test_skill_job" not in cron_manager.jobs
