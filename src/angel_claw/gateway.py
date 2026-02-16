from fastapi import FastAPI, HTTPException
from .models import AgentRequest, AgentResponse
from .agent import Agent
import uvicorn

app = FastAPI(title="Angel Claw Gateway")

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

def start():
    from .config import settings
    uvicorn.run(app, host=settings.host, port=settings.port)
