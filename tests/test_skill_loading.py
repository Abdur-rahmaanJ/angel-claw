import asyncio
import json
import shutil
from pathlib import Path

import pytest

from angel_claw.models import UserContext
from angel_claw.runtime.registry import TieredSkillRegistry
from angel_claw.utils import validate_public_url


@pytest.fixture
def user_root(tmp_path, monkeypatch):
    import angel_claw.utils as utils

    monkeypatch.setattr(utils, "get_user_root", lambda user_id: tmp_path)

    def forget_registry():
        shutil.rmtree(tmp_path / "skills", ignore_errors=True)

    yield tmp_path
    forget_registry()


def _registry(tmp_path):
    ctx = UserContext(
        user_id="test-user",
        email="test@example.com",
        roles=["user"],
        channel_type="web",
        channel_identifier="Thread 1",
    )
    return TieredSkillRegistry(ctx)


def _tools(registry):
    defs = asyncio.run(registry.get_tool_definitions())
    return {t["function"]["name"] for t in defs}


def test_unused_modules_are_hidden_until_loaded(user_root):
    registry = _registry(user_root)
    tools = _tools(registry)

    assert {"web_search", "web_read", "add_reminder", "schedule_task"} <= tools
    assert {"list_skill_modules", "load_skill_tools"} <= tools
    assert "list_uploaded_files" not in tools
    assert "send_email" not in tools

    assert registry.load_module("file_handler").startswith("Loaded 'file_handler'")
    assert "list_uploaded_files" in _tools(registry)
    assert registry.load_module("file_handler").startswith("'file_handler' tools")


def test_default_disabled_module_requires_explicit_enable(user_root):
    registry = _registry(user_root)
    assert "send_email" not in _tools(registry)
    assert registry.load_module("email").startswith("Error: 'email' is disabled")

    (user_root / "skill_config.json").write_text(
        json.dumps({"email": {"disabled": False}})
    )
    registry = _registry(user_root)
    assert registry.load_module("email").startswith("Loaded 'email'")
    assert "send_email" in _tools(registry)


def test_legacy_function_disable_is_respected(user_root):
    (user_root / "skill_config.json").write_text(
        json.dumps({"web_read": {"disabled": True}})
    )
    tools = _tools(_registry(user_root))
    assert "web_search" in tools
    assert "web_read" not in tools


def test_web_tools_reject_internal_urls():
    with pytest.raises(ValueError):
        validate_public_url("http://127.0.0.1:8000/x")
    with pytest.raises(ValueError):
        validate_public_url("file:///etc/passwd")
    with pytest.raises(ValueError):
        validate_public_url("http://localhost/x")
    assert validate_public_url("https://example.com/x") == "https://example.com/x"
