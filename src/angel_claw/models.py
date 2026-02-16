from pydantic import BaseModel
from typing import List, Optional, Any
from enum import Enum

class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"

class Message(BaseModel):
    role: Role
    content: str
    name: Optional[str] = None

class Conversation(BaseModel):
    messages: List[Message] = []

class AgentRequest(BaseModel):
    session_id: str
    message: str
    user_id: str
    model: Optional[str] = None

class AgentResponse(BaseModel):
    response: str
    session_id: str
