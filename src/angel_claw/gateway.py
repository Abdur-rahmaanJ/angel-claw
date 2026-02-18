from fastapi import FastAPI, HTTPException
from .models import AgentRequest, AgentResponse
from .agent import Agent
from .cron import cron_manager
from .telegram_bridge import telegram_bridge
from typing import Dict, Any
import uvicorn
import asyncio

app = FastAPI(title="Angel Claw Gateway")

@app.on_event("startup")
async def startup_event():
    # Start background workers
    asyncio.create_task(cron_manager.run())
    asyncio.create_task(telegram_bridge.run())

@app.post("/chat", response_model=AgentResponse)
async def chat(request: AgentRequest):
    try:
        agent = Agent(request.session_id, model=request.model)
        response_content = await agent.chat(request.message)
        return AgentResponse(
            response=response_content,
            session_id=request.session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/webhook")
async def handle_webhook(payload: Dict[str, Any]):
    """
    Receives an external webhook and triggers a proactive response from the agent.
    The payload should ideally include 'session_id' and 'message'.
    """
    session_id = payload.get("session_id", "default")
    message = payload.get("message", "External trigger received.")
    user_id = payload.get("user_id", "alice")
    
    try:
        agent = Agent(session_id)
        # We wrap the webhook message with context
        context_message = f"[Webhook Trigger]: {message}"
        response = await agent.chat(context_message)
        
        # Send the agent's reaction back via the proactive message mechanism
        await cron_manager._send_proactive_message(response, user_id, session_id)
        
        return {"status": "success", "agent_response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def start():
    from .config import settings
    uvicorn.run(app, host=settings.host, port=settings.port)
