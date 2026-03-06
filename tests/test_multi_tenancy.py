import asyncio
import os
import shutil
from pathlib import Path
from angel_claw.models import UserContext
from angel_claw.runtime.manager import runtime_manager
from angel_claw.models import Message, Role

async def test_multi_tenant_isolation():
    # Setup
    user1_ctx = UserContext(user_id="user1", email="user1@example.com", roles=[], channel_type="test", channel_identifier="sess1")
    user2_ctx = UserContext(user_id="user2", email="user2@example.com", roles=[], channel_type="test", channel_identifier="sess2")
    
    # 1. Test Runtime Isolation
    r1 = await runtime_manager.get_runtime(user1_ctx)
    r2 = await runtime_manager.get_runtime(user2_ctx)
    
    assert r1 != r2
    assert r1.context.user_id == "user1"
    assert r2.context.user_id == "user2"
    
    # 2. Test Vault Isolation
    r1.vault.set("API_KEY", "key1")
    r2.vault.set("API_KEY", "key2")
    
    assert r1.vault.get("API_KEY") == "key1"
    assert r2.vault.get("API_KEY") == "key2"
    
    # 3. Test History Isolation
    msg1 = Message(role=Role.USER, content="Hello from User 1")
    msg2 = Message(role=Role.USER, content="Hello from User 2")
    
    r1.add_message("sess1", msg1)
    r2.add_message("sess2", msg2)
    
    h1 = await r1.chat_history("sess1")
    h2 = await r2.chat_history("sess2")
    
    assert len(h1) == 1
    assert h1[0].content == "Hello from User 1"
    assert len(h2) == 1
    assert h2[0].content == "Hello from User 2"
    
    # 4. Test LRU Eviction (Simulation)
    # Manually set last_active to long ago for r1
    from datetime import datetime, UTC, timedelta
    r1.last_active = datetime.now(UTC) - timedelta(minutes=60)
    
    await runtime_manager.cleanup_idle_runtimes()
    
    # r1 should be evicted
    assert "user1" not in runtime_manager._runtimes
    assert "user2" in runtime_manager._runtimes
    
    # Reload r1 and check if vault persists
    r1_reloaded = await runtime_manager.get_runtime(user1_ctx)
    assert r1_reloaded.vault.get("API_KEY") == "key1"
    
    print("Multi-tenant isolation tests PASSED!")

if __name__ == "__main__":
    asyncio.run(test_multi_tenant_isolation())
