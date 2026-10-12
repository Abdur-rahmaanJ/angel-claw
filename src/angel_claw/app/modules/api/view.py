import logging
import time
from functools import wraps, lru_cache
from dataclasses import replace
from uuid import uuid4

from flask import request
from flask import jsonify
from flask import current_app
from flask_login import login_required
from flask_login import current_user
from itsdangerous import BadSignature
from itsdangerous import SignatureExpired
from itsdangerous import URLSafeTimedSerializer
from shopyo.api.module import ModuleHelp
from asgiref.sync import async_to_sync

from angel_claw.engine import AngelClawEngine
from angel_claw.models import UserContext
from angel_claw.mobile_bridge import queue_mobile_command, get_and_clear_commands, set_user_capabilities, get_user_capabilities, pop_command_meta, set_user_device_info
from init import csrf
from init import db
from modules.api.models import UsageEvent

logger = logging.getLogger("angel-claw-api")

mhelp = ModuleHelp(__file__, __name__)
blueprint = mhelp.blueprint

engine = AngelClawEngine()


@lru_cache(maxsize=1)
def _git_commit() -> str:
    """Short commit hash of the running code; 'unknown' outside a git checkout."""
    try:
        import subprocess
        from pathlib import Path
        root = Path(__file__).resolve().parents[4]
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root, capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


@blueprint.route("/version", methods=["GET"])
def api_version():
    """Public build/version probe so clients can verify what's deployed."""
    try:
        from importlib.metadata import version as pkg_version
        ver = pkg_version("angel-claw")
    except Exception:
        ver = "unknown"
    return jsonify({
        "status": "success",
        "version": ver,
        "commit": _git_commit(),
    })


def token_auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"status": "error", "message": "Missing or invalid token"}), 401
        
        token = auth_header.split(" ")[1]
        context = engine.validate_api_key(token)
        if not context:
            return jsonify({"status": "error", "message": "Invalid token"}), 401
            
        # Attach context to request for use in route
        request.user_context = context
        return f(*args, **kwargs)
    return decorated

# --- SSO (AngelClaw as identity provider for integrated apps) ---

SSO_SALT = "ask-moris-sso"
SSO_MAX_AGE = 60 * 60 * 24 * 30  # signed tokens live 30 days

_sso_failures = {}  # remote_ip -> [window_start, failed_attempts]


def _sso_throttled(ip):
    """Cheap per-IP brake: >=10 failed attempts within 60s blocks new tries."""
    now = time.monotonic()
    window, count = _sso_failures.get(ip, (now, 0))
    if now - window > 60:
        return False
    return count >= 10


def _sso_note_failure(ip):
    now = time.monotonic()
    window, count = _sso_failures.get(ip, (now, 0))
    if now - window > 60:
        window, count = now, 0
    _sso_failures[ip] = [window, count + 1]


def _sso_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=SSO_SALT)


def _sso_user_payload(user):
    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "name": user.first_name or user.username or user.email,
    }


@blueprint.route("/sso/token", methods=["POST"])
@csrf.exempt
def sso_token():
    """Exchange AngelClaw credentials for a signed SSO token.

    Lets integrated apps (e.g. ask-moris) sign people in with their
    AngelClaw account without handling passwords themselves.
    """
    ip = request.remote_addr or "?"
    if _sso_throttled(ip):
        return jsonify({"status": "error", "message": "Too many attempts, try again later"}), 429

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"status": "error", "message": "Email and password required"}), 400

    from shopyo_auth.models import User

    user = User.get_by_email(email)
    if user is None or not user.check_password(password):
        _sso_note_failure(ip)
        return jsonify({"status": "error", "message": "Invalid email or password"}), 401

    _sso_failures.pop(ip, None)
    token = _sso_serializer().dumps({"uid": str(user.id), "email": user.email})
    return jsonify({
        "status": "success",
        "token": token,
        "expires_in": SSO_MAX_AGE,
        "user": _sso_user_payload(user),
    })


@blueprint.route("/sso/key", methods=["POST"])
@csrf.exempt
def sso_key():
    """Resolve an AngelClaw API key to its owner's identity.

    Bring-your-own-key SSO: integrated apps (e.g. ask-moris) sign users in
    with a personal API key instead of asking for their password. The user
    creates the key in their own AngelClaw dashboard and pastes it into the app.
    """
    data = request.get_json(silent=True) or {}
    raw = (data.get("api_key") or "").strip()
    if not raw:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            raw = auth_header.split(" ", 1)[1].strip()
    if not raw:
        return jsonify({"status": "error", "message": "api_key required"}), 400

    context = engine.validate_api_key(raw)
    if not context:
        return jsonify({"status": "error", "message": "Invalid API key"}), 401

    from shopyo_auth.models import User

    user = None
    try:
        user = db.session.get(User, int(context.user_id))
    except (TypeError, ValueError):
        pass
    if user is not None:
        payload = _sso_user_payload(user)
    else:  # key owner no longer exists as a full user record
        payload = {
            "id": str(context.user_id),
            "email": context.email,
            "username": context.email,
            "name": context.email,
        }
    return jsonify({"status": "success", "user": payload})


@blueprint.route("/sso/verify", methods=["POST"])
@csrf.exempt
def sso_verify():
    """Introspect a token issued by /api/sso/token."""
    data = request.get_json(silent=True) or {}
    token = data.get("token")
    if not token:
        return jsonify({"status": "error", "message": "token required"}), 400

    try:
        payload = _sso_serializer().loads(token, max_age=SSO_MAX_AGE)
    except SignatureExpired:
        return jsonify({"status": "error", "message": "Token expired"}), 401
    except BadSignature:
        return jsonify({"status": "error", "message": "Invalid token"}), 401

    from shopyo_auth.models import User

    user = db.session.get(User, payload.get("uid"))
    if user is None:
        return jsonify({"status": "error", "message": "Unknown user"}), 401
    return jsonify({"status": "success", "user": _sso_user_payload(user)})


# --- Usage reporting from integrated apps ---

@blueprint.route("/usage", methods=["POST"])
@csrf.exempt
@token_auth_required
def record_usage():
    """Record a usage event reported by an integrated app (API-key auth)."""
    data = request.get_json(silent=True) or {}
    app_name = (data.get("app") or "").strip()
    event = (data.get("event") or "").strip()
    if not app_name or not event:
        return jsonify({"status": "error", "message": "app and event required"}), 400

    try:
        quantity = int(data.get("quantity") or 1)
    except (TypeError, ValueError):
        quantity = 1

    subject = data.get("user") or {}
    meta = data.get("meta")
    usage = UsageEvent(
        user_id=str(subject.get("id") or ""),
        email=str(subject.get("email") or ""),
        app=app_name[:100],
        event=event[:100],
        quantity=max(quantity, 1),
        reported_by=request.user_context.user_id,
        meta_json=meta if isinstance(meta, dict) else None,
    )
    db.session.add(usage)
    db.session.commit()
    return jsonify({"status": "success", "id": usage.id})


@blueprint.route("/usage/summary")
def usage_summary():
    """Usage aggregates — dashboard session or API-key auth."""
    if not current_user.is_authenticated:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"status": "error", "message": "unauthorized"}), 401
        if not engine.validate_api_key(auth_header.split(" ", 1)[1]):
            return jsonify({"status": "error", "message": "unauthorized"}), 401

    from sqlalchemy import func

    total_events, total_quantity = db.session.query(
        func.count(UsageEvent.id), func.coalesce(func.sum(UsageEvent.quantity), 0)
    ).one()

    by_app = [
        {"app": r[0], "events": r[1], "quantity": r[2]}
        for r in db.session.query(
            UsageEvent.app,
            func.count(UsageEvent.id),
            func.coalesce(func.sum(UsageEvent.quantity), 0),
        ).group_by(UsageEvent.app).all()
    ]
    by_event = [
        {"event": r[0], "events": r[1], "quantity": r[2]}
        for r in db.session.query(
            UsageEvent.event,
            func.count(UsageEvent.id),
            func.coalesce(func.sum(UsageEvent.quantity), 0),
        ).group_by(UsageEvent.event).all()
    ]
    by_user = [
        {
            "user_id": r[0],
            "email": r[1],
            "events": r[2],
            "quantity": r[3],
            "last_used": r[4].isoformat(sep=" ", timespec="seconds") if r[4] else None,
        }
        for r in db.session.query(
            UsageEvent.user_id,
            UsageEvent.email,
            func.count(UsageEvent.id),
            func.coalesce(func.sum(UsageEvent.quantity), 0),
            func.max(UsageEvent.created_at),
        )
        .group_by(UsageEvent.user_id, UsageEvent.email)
        .order_by(func.coalesce(func.sum(UsageEvent.quantity), 0).desc())
        .all()
    ]
    daily = [
        {"day": str(r[0]), "quantity": r[1]}
        for r in db.session.query(
            func.date(UsageEvent.created_at),
            func.coalesce(func.sum(UsageEvent.quantity), 0),
        )
        .group_by(func.date(UsageEvent.created_at))
        .order_by(func.date(UsageEvent.created_at))
        .all()
    ]
    recent = [
        {
            "app": r.app,
            "event": r.event,
            "email": r.email,
            "quantity": r.quantity,
            "created_at": r.created_at.isoformat(sep=" ", timespec="seconds") if r.created_at else None,
            "meta": r.meta_json,
        }
        for r in UsageEvent.query.order_by(UsageEvent.id.desc()).limit(50).all()
    ]

    return jsonify({
        "status": "success",
        "total_events": int(total_events),
        "total_quantity": int(total_quantity),
        "by_app": by_app,
        "by_event": by_event,
        "by_user": by_user,
        "daily": daily,
        "recent": recent,
    })


# --- Mobile API Endpoints ---

@blueprint.route("/mobile/messages", methods=["GET"])
@csrf.exempt
@token_auth_required
def mobile_list_messages():
    """List internal messages for the authenticated user."""
    from modules.agent.models import InternalMessage
    from shopyo_auth.models import User
    from init import db

    user_id = request.user_context.user_id
    messages = (
        InternalMessage.query.filter_by(recipient_id=user_id)
        .order_by(InternalMessage.created_at.desc())
        .limit(50)
        .all()
    )

    results = []
    for msg in messages:
        sender = db.session.get(User, msg.sender_id)
        results.append(
            {
                "id": msg.id,
                "sender_email": sender.email if sender else "Unknown",
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
                "is_read": msg.is_read,
            }
        )
    return jsonify({"status": "success", "messages": results})

@blueprint.route("/mobile/chat", methods=["POST"])
@csrf.exempt
@token_auth_required
def mobile_chat():
    """Talk to the agent via mobile API."""
    data = request.get_json()
    message = data.get("message")
    session_id = data.get("session_id")
    # Integrations (ask-moris) send one-shot blend prompts: ephemeral sessions
    # are scrubbed after the run so they never show up in the chat UI.
    ephemeral = bool(data.get("ephemeral"))

    if not message:
        return jsonify({"status": "error", "message": "Message is required"}), 400

    if not session_id:
        if ephemeral:
            # unique per request; never collides with "Thread N" numbering
            session_id = f"e-{uuid4().hex[:12]}"
        else:
            # New chat: mint the next "Thread N" (same convention as the web UI),
            # skipping existing threads so histories never collide.
            sessions = engine.get_chat_sessions(request.user_context)
            nums = []
            for s in sessions:
                sid = s.get("id", "")
                if sid.startswith("Thread "):
                    try:
                        nums.append(int(sid.split(" ", 1)[1]))
                    except ValueError:
                        pass
            session_id = f"Thread {max(nums, default=0) + 1}"

    # UserContext is frozen, so use replace
    user_context = replace(
        request.user_context,
        channel_type="mobile",
        channel_identifier=session_id
    )

    try:
        response = async_to_sync(engine.execute)(user_context, message)
        return jsonify({
            "status": "success",
            "response": response.content,
            "session_id": session_id
        })
    except Exception as e:
        logger.error(f"Error in mobile chat: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if ephemeral:
            # messages were written synchronously during execute; drop them so
            # the thread list (web + mobile) never shows integration traffic
            try:
                engine.delete_chat_session(user_context, session_id)
            except Exception as exc:  # pragma: no cover - best effort
                logger.warning(f"Could not clear ephemeral session: {exc}")

@blueprint.route("/mobile/commands", methods=["GET"])
@csrf.exempt
@token_auth_required
def mobile_list_commands():
    """Get pending automation commands for the device."""
    user_id = request.user_context.user_id
    commands = get_and_clear_commands(user_id)
    return jsonify({"status": "success", "commands": commands})

@blueprint.route("/mobile/commands/result", methods=["POST"])
@csrf.exempt
@token_auth_required
def mobile_command_result():
    """Report the result of an automation command.

    When the device attaches a `result` payload (e.g. contact data it looked
    up), the assistant gets a follow-up turn in the original thread so it can
    relay the outcome to the user; the follow-up text is returned to the app.
    """
    data = request.get_json() or {}
    command_id = data.get("command_id")
    status = data.get("status")
    result = data.get("result")
    logger.info(f"Command {command_id} result: {status}{' - ' + str(result) if result else ''}")

    followup = None
    if result:
        meta = pop_command_meta(command_id)
        if meta and meta.get("session_id"):
            try:
                user_context = replace(
                    request.user_context,
                    channel_type="mobile",
                    channel_identifier=meta["session_id"],
                )
                prompt = (
                    f"[automation-result] My phone just finished running the automation "
                    f"command '{meta.get('type')}' and reported:\n{result}\n\n"
                    "Tell the user the outcome in 1-3 natural sentences. "
                    "If it contains contact details (numbers, emails), present them clearly."
                )
                response = async_to_sync(engine.execute)(user_context, prompt)
                followup = response.content
            except Exception as e:
                logger.error(f"Follow-up after command {command_id} failed: {e}")

    return jsonify({"status": "success", "followup": followup})


@blueprint.route("/mobile/capabilities", methods=["POST"])
@csrf.exempt
@token_auth_required
def api_mobile_capabilities():
    """Mobile app reports what it can actually do right now (live capability list)."""
    data = request.get_json() or {}
    caps = data.get("capabilities", [])
    set_user_capabilities(request.user_context.user_id, caps)
    if data.get("device"):
        set_user_device_info(request.user_context.user_id, data.get("device"))
    return jsonify({"status": "success"})


# --- Chat History & Skills API ---

@blueprint.route("/chat/sessions", methods=["GET"])
@csrf.exempt
@token_auth_required
def api_get_chat_sessions():
    """List all chat threads/sessions."""
    sessions = engine.get_chat_sessions(request.user_context)
    return jsonify({"status": "success", "sessions": sessions})


@blueprint.route("/chat/history/<session_id>", methods=["GET"])
@csrf.exempt
@token_auth_required
def api_get_chat_history(session_id):
    """Get message history for a specific session."""
    # engine.get_history reads the session from context.channel_identifier
    # (UserContext is frozen), so rebuild the context with the session.
    user_context = replace(
        request.user_context, channel_identifier=session_id
    )
    history = engine.get_history(user_context)
    return jsonify({
        "status": "success", 
        "history": [m.model_dump() for m in history]
    })


@blueprint.route("/skills", methods=["GET"])
@csrf.exempt
@token_auth_required
def api_get_skills():
    """List available skills and their current config."""
    from angel_claw.runtime.registry import TieredSkillRegistry
    from angel_claw.utils import get_user_root
    import json

    user_context = request.user_context
    registry = TieredSkillRegistry(user_context)
    skills = registry.manager.get_skill_details()

    user_root = get_user_root(user_context.user_id)
    skill_config_file = user_root / "skill_config.json"
    skill_config = {}
    if skill_config_file.exists():
        try:
            skill_config = json.load(open(skill_config_file))
        except:
            pass

    skills_list = []
    for name, desc in skills.items():
        skills_list.append({
            "name": name,
            "description": desc,
            "enabled": not skill_config.get(name, {}).get("disabled", False)
        })

    return jsonify({"status": "success", "skills": skills_list})


@blueprint.route("/skills/toggle", methods=["POST"])
@csrf.exempt
@token_auth_required
def api_toggle_skill():
    """Enable or disable a specific skill."""
    data = request.get_json()
    skill_name = data.get("skill")
    enabled = data.get("enabled", True)

    if not skill_name:
        return jsonify({"status": "error", "message": "Skill name required"}), 400

    from angel_claw.utils import get_user_root
    import json

    user_context = request.user_context
    user_root = get_user_root(user_context.user_id)
    skill_config_file = user_root / "skill_config.json"

    skill_config = {}
    if skill_config_file.exists():
        try:
            skill_config = json.load(open(skill_config_file))
        except:
            pass

    if skill_name not in skill_config:
        skill_config[skill_name] = {}

    skill_config[skill_name]["disabled"] = not enabled

    with open(skill_config_file, "w") as f:
        json.dump(skill_config, f)

    return jsonify({"status": "success", "enabled": enabled})


@blueprint.route("/mobile/command/add", methods=["POST"])

@login_required
def mobile_add_command():
    """Add a command to the mobile queue (called from Web UI)."""
    data = request.get_json()
    target_user_id = data.get("user_id", str(current_user.id))
    command = data.get("command")
    
    queue_mobile_command(
        target_user_id, 
        command.get("type"), 
        command.get("params")
    )
    return jsonify({"status": "success"})

@blueprint.route("/mobile/pair", methods=["POST"])
@csrf.exempt
def mobile_pair():
    """Exchange a pairing token for a permanent API key."""
    data = request.get_json()
    token = data.get("token")
    device_name = data.get("device_name", "Android Device")

    if not token:
        return jsonify({"status": "error", "message": "Token is required"}), 400

    # Accept permanent API keys directly (ac_v1_...) - skip pairing exchange
    if token.startswith("ac_v1_"):
        api_ctx = engine.validate_api_key(token)
        if api_ctx:
            return jsonify({"status": "success", "api_key": token})

    user_id = engine.validate_pair_token(token)
    if not user_id:
        return jsonify({"status": "error", "message": "Invalid or expired token"}), 401

    from shopyo_auth.models import User
    from init import db

    user = db.session.get(User, user_id)
    context = UserContext(
        user_id=str(user.id),
        email=user.email,
        roles=[r.name for r in user.roles],
        channel_type="api",
        channel_identifier=f"mobile-{device_name}",
    )

    api_key = engine.create_api_key(context, f"Mobile: {device_name}")

    from modules.agent.models import PairingToken
    pt = PairingToken.query.filter_by(token=token).first()
    if pt:
        pt.consumed = True
        db.session.commit()

    return jsonify({"status": "success", "api_key": api_key})

@blueprint.route("/mobile/login", methods=["POST"])
@csrf.exempt
def mobile_login():
    """Authenticate with email/password and return a permanent API key."""
    data = request.get_json()
    email = data.get("email")
    password = data.get("pass")
    device_name = data.get("device_name", "Android Device")

    if not email or not password:
        return jsonify({"status": "error", "message": "Email and password required"}), 400

    from shopyo_auth.models import User

    user = User.get_by_email(email)
    if user is None or not user.check_password(password):
        return jsonify({"status": "error", "message": "Invalid credentials"}), 401

    context = UserContext(
        user_id=str(user.id),
        email=user.email,
        roles=[r.name for r in user.roles],
        channel_type="api",
        channel_identifier=f"mobile-{device_name}",
    )

    api_key = engine.create_api_key(context, f"Mobile: {device_name}")

    return jsonify({"status": "success", "api_key": api_key})

# --- General API Endpoints (moved from agent) ---

@blueprint.route("/credits")
@login_required
def get_credits():
    from angel_claw.credits import credits_enabled, get_user_stats

    user_id = str(current_user.id)
    if credits_enabled():
        credit_info = get_user_stats(user_id)
    else:
        credit_info = {"balance": 0, "limit": 0, "lifetime_spent": 0}
    return jsonify(credit_info)

@blueprint.route("/system/mcp")
@login_required
def get_mcp_status():
    from angel_claw.mcp_manager import mcp_manager
    return jsonify({"servers": mcp_manager.get_diagnostics()})

@blueprint.route("/pair-token", methods=["POST"])
@login_required
def generate_pair_token():
    user_context = _build_context()
    try:
        token = engine.generate_pair_token(user_context)
        return jsonify({"token": token})
    except Exception as e:
        logger.error(f"Error generating pair token: {e}")
        return jsonify({"error": str(e)}), 500

@blueprint.route("/api-key", methods=["POST"])
@login_required
def create_api_key():
    data = request.get_json()
    name = data.get("name")
    if not name:
        return jsonify({"error": "Key name is required"}), 400
    user_context = _build_context()
    try:
        raw_key = engine.create_api_key(user_context, name)
        return jsonify({"key": raw_key})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@blueprint.route("/api-key/revoke/<key_id>", methods=["POST"])
@login_required
def revoke_api_key(key_id):
    user_context = _build_context()
    try:
        engine.revoke_api_key(user_context, key_id)
        return jsonify({"result": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def _build_context(session_id=None):
    if session_id is None:
        session_id = request.args.get("session_id", "api-default")
    return UserContext(
        user_id=str(current_user.id),
        email=current_user.email,
        roles=[r.name for r in current_user.roles] if hasattr(current_user, "roles") else [],
        channel_type="api",
        channel_identifier=session_id,
    )
