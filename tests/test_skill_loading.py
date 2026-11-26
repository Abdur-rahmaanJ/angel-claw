import asyncio
import json
import os
import shutil
import socket
import time
from pathlib import Path

import pytest

from angel_claw.models import UserContext
from angel_claw.runtime.registry import TieredSkillRegistry
from angel_claw.utils import validate_public_url, validate_public_url_resolved


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


def test_invalid_config_keeps_last_valid_config(user_root):
    config_file = user_root / "skill_config.json"
    config_file.write_text(json.dumps({"web_read": {"disabled": True}}))
    registry = _registry(user_root)
    assert "web_read" not in _tools(registry)

    config_file.write_text("{not valid json")
    later = time.time() + 5
    os.utime(config_file, (later, later))

    assert registry.get_skill_config()["web_read"]["disabled"] is True
    assert "web_read" not in _tools(registry)


def test_load_module_preserves_discovered_case(user_root):
    skills_dir = user_root / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "MySkill.py").write_text(
        "from angel_claw.skills.manager import skill\n\n"
        "@skill\n"
        "def my_custom_tool():\n"
        "    \"\"\"A custom tool.\"\"\"\n"
        "    return 'ok'\n"
    )
    registry = _registry(user_root)

    assert registry.load_module("MySkill").startswith("Loaded 'MySkill'")
    assert "my_custom_tool" in _tools(registry)


def test_resolved_url_rejects_private_dns(monkeypatch):
    def private_dns(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

    monkeypatch.setattr(socket, "getaddrinfo", private_dns)
    with pytest.raises(ValueError, match="internal addresses"):
        asyncio.run(validate_public_url_resolved("http://looks-public.test/x"))


def test_resolved_url_rejects_mixed_public_and_private_dns(monkeypatch):
    def mixed_dns(host, port, *args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", port)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", mixed_dns)
    with pytest.raises(ValueError, match="internal addresses"):
        asyncio.run(validate_public_url_resolved("http://mixed.test/x"))


def test_dns_checked_again_for_each_redirect(monkeypatch):
    import angel_claw.skills.web as web

    seen = []

    async def check(url):
        seen.append(url)
        if "internal.test" in url:
            raise ValueError("internal addresses are not allowed")
        return url

    class FakeResponse:
        status_code = 302
        headers = {"location": "http://internal.test/admin"}
        encoding = None
        is_redirect = True

    class FakeStream:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, *args):
            return False

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def stream(self, *args, **kwargs):
            return FakeStream()

    monkeypatch.setattr(web, "validate_public_url_resolved", check)
    monkeypatch.setattr(web.httpx, "AsyncClient", FakeClient)

    with pytest.raises(ValueError, match="internal addresses"):
        asyncio.run(web._http_read("https://public.test/start"))
    assert seen == ["https://public.test/start", "http://internal.test/admin"]


def test_http_read_caps_streamed_body(monkeypatch):
    import angel_claw.skills.web as web

    async def allow(url):
        return url

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "text/plain"}
        encoding = "utf-8"
        is_redirect = False

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            yield b"a" * 8
            yield b"b" * 8

    class FakeStream:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, *args):
            return False

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def stream(self, *args, **kwargs):
            return FakeStream()

    monkeypatch.setattr(web, "validate_public_url_resolved", allow)
    monkeypatch.setattr(web.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(web, "_MAX_HTTP_BYTES", 10)

    assert asyncio.run(web._http_read("https://public.test/")) == "a" * 8 + "b" * 2


def test_lazy_loading_tools_run_on_host_in_docker(user_root, monkeypatch):
    from unittest.mock import AsyncMock

    from angel_claw.config import settings

    registry = _registry(user_root)
    monkeypatch.setattr(settings, "docker_sandboxing_enabled", True)
    docker_call = AsyncMock(return_value="docker result")
    monkeypatch.setattr(registry, "_call_in_docker", docker_call)

    result = asyncio.run(
        registry.call_tool("load_skill_tools", {"module": "file_handler"}, "Thread 1")
    )
    assert not docker_call.called
    assert result != "docker result"
