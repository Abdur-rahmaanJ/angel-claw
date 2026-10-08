import asyncio
import importlib.util
import json
import logging
import os
import pathlib
import tempfile

from flask import render_template
from flask import request
from flask_login import current_user
from flask_login import login_required

from shopyo.api.module import ModuleHelp

mhelp = ModuleHelp(__file__, __name__)
blueprint = mhelp.blueprint

logger = logging.getLogger("angel-claw-configs")

# Schema of every .env variable, see docs/configuration.md
_schema_path = pathlib.Path(__file__).with_name("schema.py")
_schema_spec = importlib.util.spec_from_file_location("configs_schema", _schema_path)
_schema = importlib.util.module_from_spec(_schema_spec)
_schema_spec.loader.exec_module(_schema)

SECTIONS = _schema.SECTIONS
FIELDS = _schema.FIELDS
FIELD_BY_KEY = _schema.FIELD_BY_KEY
JSON_KEYS = _schema.JSON_KEYS
NUMBER_KEYS = _schema.NUMBER_KEYS
CHECKBOX_KEYS = _schema.CHECKBOX_KEYS
LLM_KEYS = _schema.LLM_KEYS


def _admin_required(fn):
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, "is_admin", False):
            return render_template("configs/denied.html", **mhelp.context()), 403
        return fn(*args, **kwargs)

    wrapper.__name__ = fn.__name__
    return wrapper


def _has_newline(*values: str) -> bool:
    """Line breaks in a value would inject extra lines into .env."""
    return any(any(c in v for c in "\r\n") for v in values)


def _env_path():
    from angel_claw.config.settings import settings

    # Same resolution as pydantic-settings: ".env" relative to CWD
    return settings.model_config.get("env_file", ".env")


def _read_env_file():
    """Parse .env into {KEY: value}, preserving order. Missing file -> {}."""
    values = {}
    try:
        with open(_env_path(), "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip()
    except FileNotFoundError:
        pass
    return values


def _upsert_env_file(updates: dict):
    """Update/add keys in .env, keeping comments and unknown keys intact."""
    for key, val in updates.items():
        if _has_newline(str(key), str(val)):
            raise ValueError(f"refusing newline in env value: {key!r}")

    path = _env_path()
    try:
        with open(path, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    remaining = dict(updates)
    new_lines = []
    for line in lines:
        stripped = line.strip()
        key = None
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            new_lines.append(f"{key}={remaining.pop(key)}\n")
        else:
            new_lines.append(line)
    for key, val in remaining.items():
        new_lines.append(f"{key}={val}\n")

    # Atomic replace: a crash mid-write must never corrupt .env
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".env.tmp.")
    try:
        with os.fdopen(fd, "w") as f:
            f.writelines(new_lines)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _ensure_env_file():
    """Create .env with the documented defaults when it does not exist."""
    path = _env_path()
    if not os.path.exists(path):
        _upsert_env_file(_schema.defaults())
        logger.info(f"created missing env file at {path}")


def _sections_view(get_value):
    """Render schema sections with a display value for each field."""
    sections = []
    for section in SECTIONS:
        fields = []
        for field in section["fields"]:
            raw = get_value(field["key"], field.get("default", ""))
            view_field = dict(field)
            if field.get("secret"):
                view_field["value"] = ""
                view_field["masked"] = _mask(raw)
            else:
                view_field["value"] = raw
                view_field["masked"] = ""
            fields.append(view_field)
        sections.append(
            {"name": section["name"], "title": section["title"], "fields": fields}
        )
    return sections


def _current_config():
    env = _read_env_file()
    return {
        "model": env.get("MODEL", "openai/gpt-4o-mini"),
        "api_key": env.get("MODEL_KEY", ""),
        "api_key_masked": _mask(env.get("MODEL_KEY", "")),
        "api_base": env.get("MODEL_BASE_URL", ""),
        "sections": _sections_view(lambda key, default="": env.get(key, default)),
    }


def _config_from_form(form):
    """Same shape as _current_config but values come from a submitted form."""
    env = _read_env_file()

    def get_value(key, default=""):
        field = FIELD_BY_KEY[key]
        if field["type"] == "checkbox":
            return "True" if form.get(key) else "False"
        value = form.get(key)
        if value is None:
            return default
        value = value.strip()
        if field.get("secret") and not value:
            return env.get(key, default)
        return value

    return {
        "model": get_value("MODEL"),
        "api_key": get_value("MODEL_KEY"),
        "api_key_masked": _mask(get_value("MODEL_KEY")),
        "api_base": get_value("MODEL_BASE_URL"),
        "sections": _sections_view(get_value),
    }


def _collect_updates(form):
    """Map submitted form values to .env keys.

    - checkboxes always write True/False
    - blank secret fields keep the existing value
    """
    env = _read_env_file()
    updates = {}
    for field in FIELDS:
        key = field["key"]
        if field["type"] == "checkbox":
            updates[key] = "True" if form.get(key) else "False"
            continue
        value = (form.get(key) or "").strip()
        if field.get("secret") and not value:
            if key in env:
                continue  # blank = keep existing secret
            updates[key] = ""
            continue
        updates[key] = value
    return updates


def _validate_updates(updates):
    """Return an error message, or None when everything looks sane."""
    if _has_newline(*[str(v) for v in updates.values()]):
        return "Line breaks are not allowed in values."

    for key in NUMBER_KEYS:
        value = updates.get(key, "")
        if value:
            try:
                int(value)
            except ValueError:
                return f"{key} must be a number."

    for key in JSON_KEYS:
        value = updates.get(key, "")
        if value:
            try:
                json.loads(value)
            except ValueError:
                return f"{key} must be valid JSON."

    if not updates.get("MODEL"):
        return "Model is required."

    if not updates.get("MODEL_KEY") and not _read_env_file().get("MODEL_KEY"):
        return "API key is required."

    return None


def _apply_to_settings(updates):
    """Hot-update the live settings object so all workers see it without restart."""
    from angel_claw.config.settings import settings

    aliases = {}
    for name, field_info in type(settings).model_fields.items():
        alias = getattr(field_info, "validation_alias", None) or name
        aliases[str(alias).upper()] = name

    if updates.get("MODEL"):
        settings.model = updates["MODEL"]
    if updates.get("MODEL_KEY"):
        settings.api_key = updates["MODEL_KEY"]
    if "MODEL_BASE_URL" in updates:
        settings.api_base = updates["MODEL_BASE_URL"] or None

    for key, value in updates.items():
        if key in LLM_KEYS or key not in aliases:
            continue
        try:
            if key in CHECKBOX_KEYS:
                setattr(
                    settings,
                    aliases[key],
                    str(value).lower() in ("true", "1", "yes", "on"),
                )
            elif key in NUMBER_KEYS:
                setattr(settings, aliases[key], int(value))
            else:
                setattr(settings, aliases[key], value)
        except (TypeError, ValueError, AttributeError):
            logger.warning(f"could not hot-apply {key} to settings, restart needed")


def _validate(model, api_key, api_base):
    from angel_claw.config.validator import validate_llm

    return asyncio.run(
        validate_llm(model, api_key, api_base or None)
    )


@blueprint.route("/", methods=["GET"])
@login_required
@_admin_required
def index():
    _ensure_env_file()
    context = mhelp.context()
    context.update(
        {
            "config": _current_config(),
            "message": request.args.get("message"),
            "error": request.args.get("error"),
        }
    )
    return render_template("configs/index.html", **context)


@blueprint.route("/test", methods=["POST"])
@login_required
@_admin_required
def test():
    model = (request.form.get("MODEL") or "").strip()
    api_key = (request.form.get("MODEL_KEY") or "").strip()
    api_base = (request.form.get("MODEL_BASE_URL") or "").strip()

    if _has_newline(model, api_key, api_base):
        return _render_form(
            config=_config_from_form(request.form),
            error="Line breaks are not allowed in values.",
        )

    # Blank key field = test against the stored key
    api_key = api_key or _read_env_file().get("MODEL_KEY", "")

    if not model or not api_key:
        return _render_form(
            config=_config_from_form(request.form),
            error="Model and API key are required for testing.",
        )

    ok, msg = _validate(model, api_key, api_base)
    return _render_form(
        config=_config_from_form(request.form),
        message=f"Test OK: {msg}" if ok else f"Test failed: {msg}",
        error=None if ok else f"Test failed: {msg}",
    )


@blueprint.route("/save", methods=["POST"])
@login_required
@_admin_required
def save():
    _ensure_env_file()
    updates = _collect_updates(request.form)

    error = _validate_updates(updates)
    if error:
        return _render_form(config=_config_from_form(request.form), error=error)

    env = _read_env_file()
    model = updates.get("MODEL", "")
    api_key = updates.get("MODEL_KEY") or env.get("MODEL_KEY", "")
    api_base = updates.get("MODEL_BASE_URL", "")

    # Only hit the network when the LLM settings actually changed
    llm_changed = any(
        (updates.get(key) or "") != (env.get(key, "") or "") for key in LLM_KEYS
    )
    if llm_changed:
        ok, msg = _validate(model, api_key, api_base)
        if not ok:
            return _render_form(
                config=_config_from_form(request.form),
                error=f"Validation failed, not saved: {msg}",
            )

    _upsert_env_file(updates)
    _apply_to_settings(updates)

    logger.info(
        f"Config updated by {current_user.email}: "
        f"{', '.join(sorted(updates))}"
    )
    return _render_form(
        config=_current_config(),
        message="Saved to .env. Restart gunicorn to apply in all workers.",
    )


def _render_form(config=None, message=None, error=None):
    context = mhelp.context()
    context.update(
        {
            "config": config or _current_config(),
            "message": message,
            "error": error,
        }
    )
    return render_template("configs/index.html", **context)
