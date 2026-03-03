import pytest
from angel_claw.engine import AngelClawEngine
from angel_claw.models import UserContext
from angel_claw.memory import memory_manager
import os
import shutil

@pytest.fixture
def cleanup_vaults():
    vault_dir = "./test_vaults"
    if os.path.exists(vault_dir):
        shutil.rmtree(vault_dir)
    os.makedirs(vault_dir)
    # Monkeypatch settings
    from angel_claw.config import settings
    settings.memory_persist_dir = vault_dir
    settings.user_data_root = vault_dir
    yield
    if os.path.exists(vault_dir):
        shutil.rmtree(vault_dir)

@pytest.mark.asyncio
async def test_engine_memory_flow(cleanup_vaults):
    user_id = "test_user"
    session_id = "test_session"
    engine = AngelClawEngine()
    
    context = UserContext(
        user_id=user_id,
        email="test@local",
        roles=["user"],
        channel_type="test",
        channel_identifier=session_id
    )
    
    # We can't easily test actual LLM calls without mock/keys
    # But we can test if memory is being initialized
    memos = memory_manager.get_memos(user_id, session_id)
    assert memos is not None
    # Memory path is now user-isolated: {user_data_root}/users/{user_id}/memory/{session_id}
    assert os.path.exists(f"./test_vaults/users/{user_id}/memory/{session_id}")
