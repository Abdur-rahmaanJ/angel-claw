from pydantic import BaseModel, Field
from typing import Any, Callable, Awaitable
import uuid

class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lane_key: str
    data: Any
    execute_func: Callable[[Any], Awaitable[Any]]
