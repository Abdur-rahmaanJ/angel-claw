import importlib.util
import pathlib
import re

VIEW_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / "view.py"
)
DOCS_ENV = (
    pathlib.Path(__file__).resolve().parents[6] / "docs" / "configuration.md"
)


def _load_view():
    spec = importlib.util.spec_from_file_location("configs_view", VIEW_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_upsert_creates_file_and_keys(tmp_path, monkeypatch):
    view = _load_view()
    env = tmp_path / ".env"
    monkeypatch.setattr(view, "_env_path", lambda: str(env))

    view._upsert_env_file({"MODEL": "openai/gpt-4o", "MODEL_KEY": "sk-abc"})

    content = env.read_text()
    assert "MODEL=openai/gpt-4o" in content
    assert "MODEL_KEY=sk-abc" in content


def test_upsert_updates_existing_and_keeps_other_lines(tmp_path, monkeypatch):
    view = _load_view()
    env = tmp_path / ".env"
    env.write_text("# comment\nMODEL=old/model\nMODEL_KEY=old-key\nBRAVE_API_KEY=keep-me\n")
    monkeypatch.setattr(view, "_env_path", lambda: str(env))

    view._upsert_env_file({"MODEL": "new/model", "MODEL_BASE_URL": "http://x"})

    lines = env.read_text().splitlines()
    assert "# comment" in lines
    assert "MODEL=new/model" in lines
    assert "MODEL_KEY=old-key" in lines  # untouched key preserved
    assert "BRAVE_API_KEY=keep-me" in lines
    assert "MODEL_BASE_URL=http://x" in lines
    assert not any(l.startswith("MODEL=old") for l in lines)


def test_read_env(tmp_path, monkeypatch):
    view = _load_view()
    env = tmp_path / ".env"
    env.write_text("MODEL=m\n# c\n\nMODEL_KEY=k\n")
    monkeypatch.setattr(view, "_env_path", lambda: str(env))

    assert view._read_env_file() == {"MODEL": "m", "MODEL_KEY": "k"}


def test_read_env_missing_file(tmp_path, monkeypatch):
    view = _load_view()
    monkeypatch.setattr(view, "_env_path", lambda: str(tmp_path / "nope.env"))

    assert view._read_env_file() == {}


def test_mask():
    view = _load_view()
    assert view._mask("") == ""
    assert view._mask("short") == "*****"
    key = "sk-1234567890abcdef"
    masked = view._mask(key)
    assert masked.startswith("sk-1")
    assert masked.endswith("cdef")
    assert "1234567890" not in masked


def test_has_newline_detects_injection():
    view = _load_view()
    assert not view._has_newline("clean value")
    assert not view._has_newline("clean", "value")
    assert view._has_newline("x\nMODEL=evil")
    assert view._has_newline("x\r\nTELEGRAM_TOKEN=stolen")
    assert view._has_newline("ok", "bad\nline")


def test_upsert_rejects_newline(tmp_path, monkeypatch):
    view = _load_view()
    env = tmp_path / ".env"
    env.write_text("MODEL=safe\n")
    monkeypatch.setattr(view, "_env_path", lambda: str(env))

    try:
        view._upsert_env_file({"MODEL": "x\nEVIL=1"})
        raise AssertionError("should have raised")
    except ValueError:
        pass

    assert env.read_text() == "MODEL=safe\n"  # untouched


def test_schema_covers_every_documented_env_key():
    """Every variable in docs/configuration.md must have a config field."""
    keys = set(re.findall(r"^\|\s*`([A-Z0-9_]+)`", DOCS_ENV.read_text(), re.M))
    view = _load_view()

    assert keys, "no keys parsed from docs/configuration.md"
    assert keys == set(view.FIELD_BY_KEY)


def test_ensure_env_file_creates_missing_file(tmp_path, monkeypatch):
    view = _load_view()
    env = tmp_path / ".env"
    monkeypatch.setattr(view, "_env_path", lambda: str(env))

    view._ensure_env_file()

    content = env.read_text()
    assert "MODEL=openai/gpt-4o-mini" in content
    assert "PORT=8000" in content
    assert "CACHE_TTL=3600" in content


def test_ensure_env_file_keeps_existing_file(tmp_path, monkeypatch):
    view = _load_view()
    env = tmp_path / ".env"
    env.write_text("MODEL=keep/me\n")
    monkeypatch.setattr(view, "_env_path", lambda: str(env))

    view._ensure_env_file()

    assert env.read_text() == "MODEL=keep/me\n"


def test_collect_updates_blank_secret_kept_checkbox_written(tmp_path, monkeypatch):
    view = _load_view()
    env = tmp_path / ".env"
    env.write_text("MODEL_KEY=sk-stored\n")
    monkeypatch.setattr(view, "_env_path", lambda: str(env))

    form = {
        "MODEL": "openai/gpt-4o",
        "MODEL_KEY": "",        # blank -> keep stored key
        "PORT": "9000",
        "DEBUG": "on",          # checked
        # WHATSAPP_ENABLED absent -> unchecked
    }
    updates = view._collect_updates(form)

    assert "MODEL_KEY" not in updates
    assert updates["MODEL"] == "openai/gpt-4o"
    assert updates["PORT"] == "9000"
    assert updates["DEBUG"] == "True"
    assert updates["WHATSAPP_ENABLED"] == "False"


def test_validate_updates_flags_bad_number_and_json(tmp_path, monkeypatch):
    view = _load_view()
    monkeypatch.setattr(view, "_env_path", lambda: str(tmp_path / ".env"))

    good = {
        "MODEL": "openai/gpt-4o-mini",
        "MODEL_KEY": "sk-x",
        "PORT": "8000",
        "MCP_SERVERS": '{"a": {"command": "npx"}}',
    }
    assert view._validate_updates(dict(good)) is None

    bad_port = dict(good, PORT="not-a-number")
    assert "must be a number" in view._validate_updates(bad_port)

    bad_json = dict(good, MCP_AUTH="{oops")
    assert "must be valid JSON" in view._validate_updates(bad_json)

    no_key = dict(good)
    del no_key["MODEL_KEY"]
    assert view._validate_updates(no_key) == "API key is required."
