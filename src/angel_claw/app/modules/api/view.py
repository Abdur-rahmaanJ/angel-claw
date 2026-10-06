import logging
from functools import wraps
from dataclasses import replace

from flask import request
from flask import jsonify
from flask_login import login_required
from flask_login import current_user
from shopyo.api.module import ModuleHelp
from asgiref.sync import async_to_sync

from angel_claw.engine import AngelClawEngine
from angel_claw.models import UserContext
from angel_claw.mobile_bridge import queue_mobile_command, get_and_clear_commands, set_user_capabilities, get_user_capabilities
from init import csrf

logger = logging.getLogger("angel-claw-api")

mhelp = ModuleHelp(__file__, __name__)
blueprint = mhelp.blueprint

engine = AngelClawEngine()

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

    if not message:
        return jsonify({"status": "error", "message": "Message is required"}), 400

    if not session_id:
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
        logger.error(f"Error in mobile chat: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

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
    """Report the result of an automation command."""
    data = request.get_json()
    command_id = data.get("command_id")
    status = data.get("status")
    logger.info(f"Command {command_id} result: {status}")
    return jsonify({"status": "success"})


@blueprint.route("/mobile/capabilities", methods=["POST"])
@csrf.exempt
@token_auth_required
def api_mobile_capabilities():
    """Mobile app reports what it can actually do right now (live capability list)."""
    data = request.get_json() or {}
    caps = data.get("capabilities", [])
    set_user_capabilities(request.user_context.user_id, caps)
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
