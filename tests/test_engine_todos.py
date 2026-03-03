import pytest
import os
import shutil
from pathlib import Path
from angel_claw.engine import AngelClawEngine
from angel_claw.models import UserContext
from angel_claw.skills.todo import add_todo

@pytest.fixture
def cleanup_vaults():
    vault_dir = "./test_vaults_todo"
    if os.path.exists(vault_dir):
        shutil.rmtree(vault_dir)
    os.makedirs(vault_dir)
    # Monkeypatch settings
    from angel_claw.config import settings
    settings.user_data_root = vault_dir
    yield
    if os.path.exists(vault_dir):
        shutil.rmtree(vault_dir)

@pytest.mark.asyncio
async def test_todo_isolation(cleanup_vaults):
    engine = AngelClawEngine()
    
    user1_ctx = UserContext(
        user_id="user1",
        email="user1@local",
        roles=["user"],
        channel_type="test",
        channel_identifier="session1"
    )
    
    user2_ctx = UserContext(
        user_id="user2",
        email="user2@local",
        roles=["user"],
        channel_type="test",
        channel_identifier="session1"
    )
    
    # Add todo for user1
    # We call the skill directly but pass user_id
    add_todo("User 1 task", session_id="session1", user_id="user1")
    
    # List todos for user1 via engine
    user1_todos = engine.list_todos(user1_ctx)
    assert len(user1_todos) == 1
    assert user1_todos[0].content == "User 1 task"
    
    # List todos for user2 via engine - should be empty
    user2_todos = engine.list_todos(user2_ctx)
    assert len(user2_todos) == 0
    
    # Verify file paths
    from angel_claw.config import settings
    u1_path = Path(settings.user_data_root).expanduser() / "users" / "user1" / "todos" / "session1.json"
    u2_path = Path(settings.user_data_root).expanduser() / "users" / "user2" / "todos" / "session1.json"
    
    assert u1_path.exists()
    assert not u2_path.exists()
