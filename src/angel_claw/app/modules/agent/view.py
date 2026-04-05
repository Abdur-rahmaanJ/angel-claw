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


def _build_context():
    # In Shopyo, current_user.id is usually what we need
    # We use session_id from request or a default for web
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
    context = mhelp.context()
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
    credit_info = {"balance": 0, "lifetime_spent": 0}
    if credits_enabled():
        credit_info = get_user_stats(user_id)

    context.update(
        {"history": history, "channels": channel_types, "credit_info": credit_info}
    )
    return render_template("{}/index.html".format(mhelp.info["module_name"]), **context)


import json


import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=2)


def run_async_streaming(user_context, message):
    """Run async generator in thread and yield chunks."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        async_gen = engine.execute_streaming(user_context, message)

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
    if not message:
        return jsonify({"error": "No message provided"}), 400

    user_context = _build_context()

    def generate():
        yield from run_async_streaming(user_context, message)

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@blueprint.route("/pair-token", methods=["POST"])
@login_required
def generate_pair_token():
    user_context = _build_context()
    try:
        token = engine.generate_pair_token(user_context)
        return jsonify({"token": token})
    except Exception as e:
        import traceback

        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@blueprint.route("/api-key", methods=["POST"])
@login_required
def create_api_key():
    data = request.get_json()
    name = data.get("name", "Default Key")
    user_context = _build_context()
    try:
        raw_key = engine.create_api_key(user_context, name)
        return jsonify({"api_key": raw_key})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route("/me")
@login_required
def me():
    from modules.agent.models import Channel, ApiKey, InternalMessage

    user_id = str(current_user.id)
    channels = Channel.query.filter_by(user_id=user_id).all()
    api_keys = ApiKey.query.filter_by(user_id=user_id).all()

    return jsonify(
        {
            "user_id": user_id,
            "email": current_user.email,
            "channels": [
                {
                    "type": c.channel_type,
                    "identifier": c.channel_identifier,
                    "last_seen": c.last_seen_at.isoformat() if c.last_seen_at else None,
                }
                for c in channels
            ],
            "api_keys": [
                {
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
    # Use the skill directly but we need to parse it if it returns string
    # For prototype, we will fetch from the skill manager
    from angel_claw.skills.todo import list_todos

    result = list_todos(
        session_id=user_context.channel_identifier, user_id=user_context.user_id
    )
    return jsonify({"todos": result})


@blueprint.route("/calendar")
@login_required
def get_calendar():
    user_context = _build_context()
    from angel_claw.skills.calendar import list_calendar_events

    result = list_calendar_events(
        session_id=user_context.channel_identifier, user_id=user_context.user_id
    )
    return jsonify({"events": result})


@blueprint.route("/messages")
@login_required
def get_messages():
    user_context = _build_context()
    from angel_claw.skills.messaging import list_unread_messages

    result = list_unread_messages(user_context.user_id, include_read=True)
    return jsonify({"messages": result})


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

    user_context = _build_context()
    registry = TieredSkillRegistry(user_context)
    skills = registry.manager.get_skill_details()
    return jsonify({"skills": skills})
