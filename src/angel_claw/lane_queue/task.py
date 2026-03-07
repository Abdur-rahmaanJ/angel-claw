from pydantic import BaseModel, Field
from typing import Any, Callable, Awaitable, Optional
import uuid

class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lane_key: str
    data: Any
    execute_func: Optional[Callable[[Any], Awaitable[Any]]] = Field(default=None, exclude=True)

    class Config:
        arbitrary_types_allowed = True
