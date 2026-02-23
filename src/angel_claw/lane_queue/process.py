import asyncio
import logging
import uuid
from typing import Dict, Any, Optional
from .queue import lane_queue
from .task import Task
from ..agent import Agent
from ..models import AgentRequest

logger = logging.getLogger("angel-claw-lane-queue-process")

results: Dict[str, Any] = {}
events: Dict[str, asyncio.Event] = {}

async def agent_chat_wrapper(request: AgentRequest):
    try:
        agent = Agent(request.session_id, model=request.model, api_base=request.api_base)
        response_content = await agent.chat(request.message)
        return response_content
    except Exception as e:
        logger.error(f"Error in agent_chat_wrapper: {e}")
        return f"Error: {str(e)}"

async def process_chat_request(request: AgentRequest) -> str:
    # 1. Unique ID for this specific request
    # NOTE: In a real persistent system, this would be an Idempotency-Key
    # from the client headers.
    req_id = str(uuid.uuid4())
    events[req_id] = asyncio.Event()

    async def execute_and_set_result(task_data: AgentRequest):
        try:
            result = await agent_chat_wrapper(task_data)
            results[req_id] = result
        finally:
            events[req_id].set()

    # 2. Wrap into a Task for the Lane Queue
    task = Task(
        task_id=req_id,
        lane_key=request.session_id,
        data=request,
        execute_func=execute_and_set_result,
    )

    try:
        # 3. Enqueue and wait
        await lane_queue.enqueue(task)
        await events[req_id].wait()
        
        # 4. Success - Return response
        response_content = results.pop(req_id)
        events.pop(req_id)
        return response_content
    except Exception as e:
        logger.error(f"Failed to process chat request {req_id}: {e}")
        events.pop(req_id, None)
        results.pop(req_id, None)
        return f"Error: {str(e)}"
