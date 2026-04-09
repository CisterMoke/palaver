from pydantic import BaseModel, Field

from palaver.app.enums import RoleEnum


class Message(BaseModel):
    sender: str
    role: RoleEnum
    content: str
    recipients: list[str] | None = None


class IncomingMessage(Message):
    sender: str = "USER"


class ChatMessage(Message):
    id: str
    chatroom_id: str
    timestamp: str

    def to_message(self) -> Message:
        return Message(**self.model_dump(exclude={"id", "chatroom_id", "timestamp"}))


class SendMessageRequest(BaseModel):
    message: Message
    history: list[Message] = Field(..., default_factory=[])