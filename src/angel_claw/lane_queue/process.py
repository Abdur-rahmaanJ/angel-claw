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
        agent = Agent(
            request.session_id, model=request.model, api_base=request.api_base
        )
        response_content = await agent.chat(request.message)
        return response_content
    except Exception as e:
        logger.error(f"Error in agent_chat_wrapper: {e}")
        return f"Error: {str(e)}"


async def process_chat_request(request: AgentRequest) -> str:
    req_id = str(uuid.uuid4())
    event = asyncio.Event()
    events[req_id] = event

    async def execute_and_set_result(task_data: AgentRequest):
        try:
            result = await agent_chat_wrapper(task_data)
            results[req_id] = result
        except Exception as e:
            logger.error(f"Error executing task {req_id}: {e}")
            results[req_id] = f"Error: {str(e)}"
        finally:
            event.set()

    task = Task(
        task_id=req_id,
        lane_key=request.session_id,
        data=request,
        execute_func=execute_and_set_result,
    )

    try:
        await lane_queue.enqueue(task)
        await event.wait()

        response_content = results.pop(req_id, None)
        if response_content is None:
            response_content = (
                f"Error: Task {req_id} completed but no result was stored"
            )
        return response_content
    except Exception as e:
        logger.error(f"Failed to process chat request {req_id}: {e}")
        return f"Error: {str(e)}"
    finally:
        events.pop(req_id, None)
        results.pop(req_id, None)
