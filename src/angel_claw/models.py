from pydantic import BaseModel
from typing import List, Optional, Any
from enum import Enum
from dataclasses import dataclass

class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"

@dataclass(frozen=True)
class UserContext:
    user_id: str          # Shopyo user.id
    email: str
    roles: List[str]
    channel_type: str      # "web" | "telegram" | "cli" | "api"
    channel_identifier: str
    is_admin: bool = False

class Message(BaseModel):
    role: Role
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Any]] = None
    tool_call_id: Optional[str] = None

class Conversation(BaseModel):
    messages: List[Message] = []

class AgentRequest(BaseModel):
    session_id: str
    message: str
    user_id: str
    model: Optional[str] = None
    api_base: Optional[str] = None

class AgentResponse(BaseModel):
    response: str
    session_id: str

class EngineResponse(BaseModel):
    content: str
    tool_calls: Optional[List[Any]] = None

class Todo(BaseModel):
    id: str
    content: str
    completed: bool
    priority: str
    due_date: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None

