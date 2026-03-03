from fastapi import FastAPI, HTTPException
from .models import AgentRequest, AgentResponse, UserContext
from .engine import AngelClawEngine
from .cron import cron_manager
from .telegram_bridge import telegram_bridge
from .whatsapp_bridge import whatsapp_bridge
from .mcp_manager import mcp_manager
from .lane_queue.queue import lane_queue
from .lane_queue.process import process_chat_request
from typing import Dict, Any, Optional
from fastapi import Request, Response
from contextlib import asynccontextmanager
import uvicorn
import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background workers
    lane_queue.start_workers()
    asyncio.create_task(cron_manager.run())
    asyncio.create_task(telegram_bridge.run())
    asyncio.create_task(whatsapp_bridge.run())
    yield
    # Shutdown logic
    await whatsapp_bridge.close()
    await mcp_manager.disconnect()


app = FastAPI(title="Angel Claw Gateway", lifespan=lifespan)


@app.post("/chat", response_model=AgentResponse)
async def chat(request: AgentRequest):
    try:
        response_content = await process_chat_request(request)
        if response_content.startswith("Error:"):
            raise HTTPException(status_code=500, detail=response_content)

        return AgentResponse(response=response_content, session_id=request.session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/webhook")
async def handle_webhook(payload: Dict[str, Any], request: Request):
    """
    Receives an external webhook and triggers a proactive response from the agent.
    The payload should ideally include 'session_id' and 'message'.
    Requires X-Webhook-Key header if WEBHOOK_KEY is configured in .env.
    """
    from .config import settings

    if settings.webhook_key:
        webhook_key = request.headers.get("X-Webhook-Key")
        if webhook_key != settings.webhook_key:
            raise HTTPException(
                status_code=401, detail="Invalid or missing webhook key"
            )

    session_id = payload.get("session_id", "default")
    message = payload.get("message", "External trigger received.")
    user_id = payload.get("user_id", "alice")
    api_base = payload.get("api_base")

    try:
        engine = AngelClawEngine()
        context = UserContext(
            user_id=user_id,
            email=f"{user_id}@angelclaw.local",
            roles=["user"],
            channel_type="webhook",
            channel_identifier=session_id
        )
        # We wrap the webhook message with context
        context_message = f"[Webhook Trigger]: {message}"
        response = await engine.execute(context, context_message)

        # Send the agent's reaction back via the proactive message mechanism
        await cron_manager._send_proactive_message(response.content, user_id, session_id)

        return {"status": "success", "agent_response": response.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def start():
    from .config import settings

    uvicorn.run(app, host=settings.host, port=settings.port)
