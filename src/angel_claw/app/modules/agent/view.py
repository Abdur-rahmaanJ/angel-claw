from flask import render_template
from flask import request
from flask import jsonify
from flask_login import login_required
from flask_login import current_user
from shopyo.api.module import ModuleHelp

from angel_claw.engine import AngelClawEngine
from angel_claw.models import UserContext

mhelp = ModuleHelp(__file__, __name__)
blueprint = mhelp.blueprint

# Shared engine instance
engine = AngelClawEngine()

def _build_context():
    # In Shopyo, current_user.id is usually what we need
    # We use session_id from request or a default for web
    session_id = request.args.get("session_id", "web-default")
    return UserContext(
        user_id=str(current_user.id),
        email=current_user.email,
        roles=[r.name for r in current_user.roles] if hasattr(current_user, "roles") else [],
        channel_type="web",
        channel_identifier=session_id
    )

@blueprint.route("/")
@login_required
def index():
    context = mhelp.context()
    user_context = _build_context()
    history = engine.get_history(user_context)
    context.update({
        "history": history
    })
    return render_template(
        "{}/index.html".format(mhelp.info["module_name"]), **context
    )

@blueprint.route("/chat", methods=["POST"])
@login_required
async def chat():
    data = request.get_json()
    message = data.get("message")
    if not message:
        return jsonify({"error": "No message provided"}), 400
    
    user_context = _build_context()
    try:
        response = await engine.execute(user_context, message)
        return jsonify({
            "response": response.content,
            "tool_calls": response.tool_calls
        })
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger("angel-claw-view")
        logger.error(f"Error in chat view: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

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


