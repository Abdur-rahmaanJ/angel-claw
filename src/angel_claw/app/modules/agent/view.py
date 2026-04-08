from flask import render_template
from flask import request
from flask import jsonify
from flask import Response
from flask import stream_with_context
from flask_login import login_required
from flask_login import current_user
from shopyo.api.module import ModuleHelp
from asgiref.sync import async_to_sync

from angel_claw.engine import AngelClawEngine
from angel_claw.models import UserContext

mhelp = ModuleHelp(__file__, __name__)
blueprint = mhelp.blueprint

engine = AngelClawEngine()


def _build_context(session_id=None):
    # In Shopyo, current_user.id is usually what we need
    # We use session_id from request or a default for web
    if session_id is None:
        session_id = request.args.get("session_id", "web-default")
    return UserContext(
        user_id=str(current_user.id),
        email=current_user.email,
        roles=[r.name for r in current_user.roles]
        if hasattr(current_user, "roles")
        else [],
        channel_type="web",
        channel_identifier=session_id,
    )


@blueprint.route("/")
@login_required
def index():
    try:
        context = mhelp.context()
        # Filter out None values that can't be JSON serialized
        context = {k: v for k, v in context.items() if v is not None}
    except:
        context = {}
    user_context = _build_context()
    # history = engine.get_history(user_context) # Cleared on reload per request
    history = []

    from modules.agent.models import Channel
    from angel_claw.credits import credits_enabled, get_user_stats, add_credits
    from angel_claw.config.settings import settings

    user_id = str(current_user.id)
    channels = Channel.query.filter_by(user_id=user_id, is_active=True).all()
    channel_types = [c.channel_type for c in channels]

    # Get credit info
    credit_info = {"balance": 0, "limit": 1000, "lifetime_spent": 0}
    if credits_enabled():
        credit_info = get_user_stats(user_id)

    # Get skill config
    from angel_claw.utils import get_user_root
    import json

    user_root = get_user_root(user_id)
    skill_config_file = user_root / "skill_config.json"
    skill_config = {}
    if skill_config_file.exists():
        try:
            skill_config = json.load(open(skill_config_file))
        except:
            pass

    # Ensure skill_config is a dict
    if not isinstance(skill_config, dict):
        skill_config = {}

    context.update(
        {
            "history": history,
            "channels": channel_types,
            "credit_info": credit_info,
            "skill_config": skill_config,
        }
    )
    return render_template("{}/index.html".format(mhelp.info["module_name"]), **context)


import json


import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=2)


def run_async_streaming(user_context, message, use_global=False):
    """Run async generator in thread and yield chunks."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        async_gen = engine.execute_streaming(
            user_context, message, use_global=use_global
        )

        while True:
            try:
                chunk = loop.run_until_complete(async_gen.__anext__())
                if chunk is not None:
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            except StopAsyncIteration:
                yield f"data: {json.dumps({'done': True})}\n\n"
                break
    except Exception as e:
        import traceback
        import logging

        logger = logging.getLogger("angel-claw-view")
        logger.error(f"Error in streaming chat: {e}")
        logger.error(traceback.format_exc())
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    finally:
        loop.run_until_complete(asyncio.sleep(0))
        loop.close()


@blueprint.route("/chat", methods=["POST"])
@login_required
def chat():
    data = request.get_json()
    message = data.get("message")
    use_global = data.get("use_global", False)
    session_id = data.get("session_id", "Thread 1")
    if not message:
        return jsonify({"error": "No message provided"}), 400

    user_context = _build_context(session_id=session_id)

    def generate():
        yield from run_async_streaming(user_context, message, use_global=use_global)

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@blueprint.route("/view/<view_name>")
@login_required
def get_view(view_name):
    context = mhelp.context()
    template = f"agent/views/{view_name}.html"
    return render_template(template, **context)


@blueprint.route("/chat/sessions")
@login_required
def chat_sessions():
    user_context = _build_context(
        session_id="Thread 1"
    )  # Use a valid session for context
    sessions = engine.get_chat_sessions(user_context)

    if request.headers.get("HX-Request"):
        current_session_id = request.args.get("current_session_id", "Thread 1")
        return render_template(
            "agent/partials/_thread_list.html",
            sessions=sessions,
            current_session_id=current_session_id,
        )
    return jsonify({"sessions": sessions})


@blueprint.route("/chat/history/<session_id>")
@login_required
def chat_history(session_id):
    user_context = _build_context(session_id=session_id)
    history = engine.get_history(user_context)
    return jsonify({"history": [m.model_dump() for m in history]})


@blueprint.route("/chat/memories")
@login_required
def chat_memories():
    session_id = request.args.get("session_id", "Thread 1")
    user_context = _build_context(session_id=session_id)
    memories = engine.get_memories(user_context)
    if request.args.get("format") == "html":
        return render_template("agent/partials/_memory_list.html", memories=memories)
    return jsonify({"memories": memories})


@blueprint.route("/chat/memories/add", methods=["POST"])
@login_required
def add_memory():
    data = request.get_json()
    content = data.get("content")
    semantic_type = data.get("type", "fact")

    if not content:
        return jsonify({"error": "Content is required"}), 400

    user_context = _build_context()
    from angel_recall import create_plaintext, SemanticType
    from angel_claw.runtime.manager import runtime_manager

    runtime = async_to_sync(runtime_manager.get_runtime)(user_context)
    memos = runtime.get_memos(user_context.channel_identifier)

    cube = create_plaintext(
        text=content,
        semantic_type=SemanticType(semantic_type),
        owner=user_context.email,
    )
    memos.api.create(cube, namespace=f"user_{user_context.email}")

    return jsonify({"result": "success"})


@blueprint.route("/chat/memories/delete/<memory_id>", methods=["POST"])
@login_required
def delete_memory(memory_id):
    session_id = request.args.get("session_id", "Thread 1")
    user_context = _build_context(session_id=session_id)
    engine.delete_memory(user_context, memory_id)
    if request.headers.get("HX-Request"):
        return "", 204
    return jsonify({"result": "success"})


@blueprint.route("/chat/delete/<session_id>", methods=["POST"])
@login_required
def delete_chat_session(session_id):
    user_context = _build_context(session_id=session_id)
    engine.delete_chat_session(user_context, session_id)
    return jsonify({"result": "success"})


@blueprint.route("/chat/session/rename", methods=["POST"])
@login_required
def rename_session():
    data = request.get_json()
    old_id = data.get("session_id")
    new_name = data.get("new_name")

    if not old_id or not new_name:
        return jsonify({"error": "session_id and new_name required"}), 400

    user_context = _build_context(session_id=old_id)
    engine.rename_chat_session(user_context, old_id, new_name)
    return jsonify({"result": "success"})


@blueprint.route("/pair-token", methods=["POST"])
@login_required
def generate_pair_token():
    user_context = _build_context()
    try:
        token = engine.generate_pair_token(user_context)
        return jsonify({"token": token})
    except Exception as e:
        import traceback

        traceback.print_exc()
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


@blueprint.route("/me")
@login_required
def me():
    from modules.agent.models import Channel, ApiKey, InternalMessage
    import subprocess

    user_id = str(current_user.id)
    channels = Channel.query.filter_by(user_id=user_id).all()
    api_keys = ApiKey.query.filter_by(user_id=user_id).all()

    # Check if the bridge service is running
    bridge_online = False
    try:
        # systemctl is-active returns 'active' and exit code 0 if running
        res = subprocess.run(
            ["systemctl", "is-active", "angel-claw-bridge.service"],
            capture_output=True,
            text=True,
        )
        bridge_online = res.stdout.strip() == "active"
    except Exception:
        pass

    # Filter channels for WhatsApp and Telegram only
    whatsapp = next((c for c in channels if c.channel_type == "whatsapp"), None)
    telegram = next((c for c in channels if c.channel_type == "telegram"), None)

    integrations = {
        "whatsapp": {
            "connected": whatsapp is not None,
            "identifier": whatsapp.channel_identifier if whatsapp else None,
        },
        "telegram": {
            "connected": telegram is not None,
            "identifier": telegram.channel_identifier if telegram else None,
        },
    }

    if request.args.get("format") == "api_keys":
        return render_template("agent/partials/_api_keys_list.html", api_keys=api_keys)
    elif request.args.get("format") == "integrations":
        return render_template(
            "agent/partials/_integrations_list.html",
            bridge_online=bridge_online,
            channels=channels,
        )

    return jsonify(
        {
            "user_id": user_id,
            "email": current_user.email,
            "bridge_online": bridge_online,
            "channels": [
                {
                    "type": c.channel_type,
                    "identifier": c.channel_identifier,
                    "last_seen": c.last_seen_at.isoformat() if c.last_seen_at else None,
                }
                for c in channels
            ],
            "integrations": integrations,
            "api_keys": [
                {
                    "id": k.id,
                    "name": k.name,
                    "prefix": k.prefix,
                    "created_at": k.created_at.isoformat() if k.created_at else None,
                }
                for k in api_keys
            ],
        }
    )


@blueprint.route("/todos")
@login_required
def get_todos():
    user_context = _build_context()
    from angel_claw.skills.todo import list_todos

    result = list_todos(
        session_id=user_context.channel_identifier, user_id=user_context.user_id
    )
    if request.args.get("format") == "html":
        return render_template("agent/partials/_todo_list.html", todos=result)
    # Return JSON for dashboard
    pending = result.count("⬜")
    total = result.count("⬜") + result.count("✅")
    return jsonify({"pending": pending, "total": max(total, 1)})


@blueprint.route("/calendar")
@login_required
def get_calendar():
    user_context = _build_context()
    from angel_claw.skills.calendar import list_calendar_events

    result = list_calendar_events(
        session_id=user_context.channel_identifier, user_id=user_context.user_id
    )
    if request.args.get("format") == "html":
        return render_template("agent/partials/_calendar_list.html", events=result)
    # Return JSON for dashboard
    lines = result.split("\n") if isinstance(result, str) else result
    upcoming = len([l for l in lines if l.strip() and not l.startswith("##")])
    return jsonify({"upcoming": upcoming, "events": result})


@blueprint.route("/messages")
@login_required
def get_messages():
    user_context = _build_context()
    from angel_claw.skills.messaging import list_unread_messages

    result = list_unread_messages(user_context.user_id, include_read=True)
    if request.args.get("format") == "html":
        return render_template("agent/partials/_message_list.html", messages=result)
    # Return JSON for dashboard
    messages = result.get("messages", []) if isinstance(result, dict) else []
    unread = len([m for m in messages if not m.get("read", False)])
    return jsonify({"unread": unread, "recipients": len(messages), "messages": result})


@blueprint.route("/messages/delete/<int:message_id>", methods=["POST"])
@login_required
def delete_message(message_id):
    user_context = _build_context()
    from angel_claw.skills.messaging import delete_internal_message

    result = delete_internal_message(
        message_id=message_id, user_id=user_context.user_id
    )
    return jsonify({"result": result})


@blueprint.route("/messages/mark-read/<int:message_id>", methods=["POST"])
@login_required
def mark_message_read(message_id):
    user_context = _build_context()
    try:
        from angel_claw.skills.messaging import mark_message_as_read

        result = mark_message_as_read(
            message_id=message_id, user_id=user_context.user_id
        )
        return jsonify({"result": result})
    except Exception as e:
        import traceback

        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@blueprint.route("/skills")
@login_required
def get_skills():
    # Use the registry to get skills including user-specific ones
    from angel_claw.runtime.registry import TieredSkillRegistry
    import importlib

    user_context = _build_context()
    registry = TieredSkillRegistry(user_context)
    skills = registry.manager.get_skill_details()

    # Get user skill config from file
    from angel_claw.utils import get_user_root
    import json

    user_root = get_user_root(user_context.user_id)
    skill_config_file = user_root / "skill_config.json"
    skill_config = {}
    if skill_config_file.exists():
        try:
            skill_config = json.load(open(skill_config_file))
        except:
            pass

    # Get skill field definitions from skill modules
    skill_field_defs = {}
    for skill_name in skills.keys():
        try:
            # Try to import the skill module and get SKILL_CONFIG
            mod = importlib.import_module(f"angel_claw.skills.{skill_name}")
            if hasattr(mod, "SKILL_CONFIG"):
                # SKILL_CONFIG is {"fields": [...]}, extract the fields array
                skill_field_defs[skill_name] = mod.SKILL_CONFIG.get("fields", [])
        except:
            pass

    if request.args.get("format") == "html":
        return render_template("agent/partials/_skills_list.html", skills=skills)

    # Convert dict to array
    skills_list = [{"name": k, "description": v} for k, v in skills.items()]
    return jsonify(
        {
            "skills": skills_list,
            "skill_config": skill_config,
            "skill_field_defs": skill_field_defs,
        }
    )


@blueprint.route("/skills/toggle", methods=["POST"])
@login_required
def toggle_skill():
    data = request.get_json()
    skill_name = data.get("skill")
    enabled = data.get("enabled", True)

    from angel_claw.utils import get_user_root
    import json

    user_context = _build_context()
    user_root = get_user_root(user_context.user_id)

    skill_config_file = user_root / "skill_config.json"
    skill_config = {}
    if skill_config_file.exists():
        skill_config = json.load(open(skill_config_file))

    if skill_name not in skill_config:
        skill_config[skill_name] = {}
    skill_config[skill_name]["disabled"] = not enabled

    json.dump(skill_config, open(skill_config_file, "w"))
    return jsonify({"result": "success"})


@blueprint.route("/skills/config", methods=["POST"])
@login_required
def save_skill_config():
    data = request.get_json()
    skill_name = data.get("skill")
    fields = data.get("fields", {})

    from angel_claw.utils import get_user_root
    import json

    user_context = _build_context()
    user_root = get_user_root(user_context.user_id)

    skill_config_file = user_root / "skill_config.json"
    skill_config = {}
    if skill_config_file.exists():
        skill_config = json.load(open(skill_config_file))

    if skill_name not in skill_config:
        skill_config[skill_name] = {}
    skill_config[skill_name]["fields"] = fields

    json.dump(skill_config, open(skill_config_file, "w"))
    return jsonify({"result": "success"})


@blueprint.route("/skills/upload", methods=["POST"])
@login_required
def upload_skill():
    if "skill_file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["skill_file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file and file.filename.endswith(".py"):
        user_context = _build_context()
        from angel_claw.utils import get_user_root

        user_root = get_user_root(user_context.user_id)
        skills_dir = user_root / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)

        file_path = skills_dir / file.filename
        file.save(str(file_path))

        # Force reload the registry for this user
        from angel_claw.runtime.manager import runtime_manager

        runtime = async_to_sync(runtime_manager.get_runtime)(user_context)
        runtime.skills.reload()

        return jsonify({"result": "success", "filename": file.filename})

    return jsonify({"error": "Only .py files are allowed"}), 400


@blueprint.route("/soul")
@login_required
def get_soul():
    user_context = _build_context()
    from angel_claw.runtime.manager import runtime_manager

    runtime = async_to_sync(runtime_manager.get_runtime)(user_context)
    if request.args.get("format") == "html":
        return render_template("agent/partials/_soul_form.html", soul=runtime.soul)
    return jsonify({"instruction": runtime.soul})


@blueprint.route("/auth/change-password", methods=["POST"])
@login_required
def change_password():
    data = request.get_json()
    old_password = data.get("old_password")
    new_password = data.get("new_password")

    if not old_password or not new_password:
        return jsonify({"error": "Missing password fields"}), 400

    from shopyo_auth.models import User
    from init import db

    user = User.query.get(current_user.id)
    if user and user.check_hash(old_password):
        user.set_hash(new_password)
        db.session.commit()
        return jsonify({"result": "success"})

    return jsonify({"error": "Invalid current password"}), 401


@blueprint.route("/soul/update", methods=["POST"])
@login_required
def update_soul():
    if request.is_json:
        data = request.get_json()
        new_soul = data.get("soul")
    else:
        new_soul = request.form.get("soul")

    if new_soul is None:
        return jsonify({"error": "No soul content provided"}), 400

    user_context = _build_context()
    from angel_claw.runtime.manager import runtime_manager

    runtime = async_to_sync(runtime_manager.get_runtime)(user_context)
    runtime.update_soul(new_soul)
    return jsonify({"result": "success"})


@blueprint.route("/soul/templates")
@login_required
def get_soul_templates():
    user_context = _build_context()
    from angel_claw.runtime.manager import runtime_manager

    runtime = async_to_sync(runtime_manager.get_runtime)(user_context)
    return jsonify({"templates": list(runtime.get_soul_templates().keys())})


@blueprint.route("/soul/templates/apply", methods=["POST"])
@login_required
def apply_soul_template():
    data = request.get_json()
    template_name = data.get("template")
    if not template_name:
        return jsonify({"error": "No template name provided"}), 400

    user_context = _build_context()
    from angel_claw.runtime.manager import runtime_manager

    runtime = async_to_sync(runtime_manager.get_runtime)(user_context)
    if runtime.apply_soul_template(template_name):
        return jsonify({"result": "success", "soul": runtime.soul})

    return jsonify({"error": "Template not found"}), 404


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
