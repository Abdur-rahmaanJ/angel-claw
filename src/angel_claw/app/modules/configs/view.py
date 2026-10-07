import asyncio
import logging
import os
import tempfile

from flask import render_template
from flask import request
from flask_login import current_user
from flask_login import login_required

from shopyo.api.module import ModuleHelp

mhelp = ModuleHelp(__file__, __name__)
blueprint = mhelp.blueprint

logger = logging.getLogger("angel-claw-configs")


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


def _current_config():
    env = _read_env_file()
    return {
        "model": env.get("MODEL", "openai/gpt-4o-mini"),
        "api_key": env.get("MODEL_KEY", ""),
        "api_key_masked": _mask(env.get("MODEL_KEY", "")),
        "api_base": env.get("MODEL_BASE_URL", ""),
    }


def _apply_to_settings(model, api_key, api_base):
    """Hot-update the live settings object so all workers see it without restart."""
    from angel_claw.config.settings import settings

    settings.model = model
    if api_key:
        settings.api_key = api_key
    settings.api_base = api_base or None


def _validate(model, api_key, api_base):
    from angel_claw.config.validator import validate_llm

    return asyncio.run(
        validate_llm(model, api_key, api_base or None)
    )


@blueprint.route("/", methods=["GET"])
@login_required
@_admin_required
def index():
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
    model = (request.form.get("model") or "").strip()
    api_key = (request.form.get("api_key") or "").strip()
    api_base = (request.form.get("api_base") or "").strip()

    if _has_newline(model, api_key, api_base):
        return _render_form(error="Line breaks are not allowed in values.")

    if not model or not api_key:
        return _render_form(error="Model and API key are required for testing.")

    ok, msg = _validate(model, api_key, api_base)
    return _render_form(
        config={"model": model, "api_key": api_key, "api_key_masked": "", "api_base": api_base},
        message=f"Test OK: {msg}" if ok else f"Test failed: {msg}",
        error=None if ok else f"Test failed: {msg}",
    )


@blueprint.route("/save", methods=["POST"])
@login_required
@_admin_required
def save():
    model = (request.form.get("model") or "").strip()
    api_key = (request.form.get("api_key") or "").strip()
    api_base = (request.form.get("api_base") or "").strip()

    if _has_newline(model, api_key, api_base):
        return _render_form(error="Line breaks are not allowed in values.")

    if not model:
        return _render_form(error="Model is required.")

    # Empty key field = keep existing key
    env = _read_env_file()
    existing_key = env.get("MODEL_KEY", "")
    if not api_key:
        api_key = existing_key
    if not api_key:
        return _render_form(error="API key is required.")

    ok, msg = _validate(model, api_key, api_base)
    if not ok:
        return _render_form(
            config={"model": model, "api_key": api_key, "api_key_masked": "", "api_base": api_base},
            error=f"Validation failed, not saved: {msg}",
        )

    _upsert_env_file(
        {"MODEL": model, "MODEL_KEY": api_key, "MODEL_BASE_URL": api_base}
    )
    _apply_to_settings(model, api_key, api_base)

    logger.info(f"Model config updated by {current_user.email}: {model} @ {api_base or 'default'}")
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
