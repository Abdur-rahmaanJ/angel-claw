import pytest
from angel_claw.agent import Agent
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
    yield
    shutil.rmtree(vault_dir)

@pytest.mark.asyncio
async def test_agent_memory_flow(cleanup_vaults):
    session_id = "test_session"
    agent = Agent(session_id)
    
    # We can't easily test actual LLM calls without mock/keys
    # But we can test if memory is being initialized
    assert agent.memos is not None
    assert os.path.exists("./test_vaults/test_session")
