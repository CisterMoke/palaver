from pydantic import BaseModel, Field


class Message(BaseModel):
    sender: str
    role: str
    content: str
    target_agent_ids: list[str] | None = None


class ChatMessage(Message):
    id: str
    chatroom_id: str
    timestamp: str


class SendMessageRequest(BaseModel):
    message: Message
    history: list[Message] = Field(..., default_factory=[])