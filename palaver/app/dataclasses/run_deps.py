from pydantic import BaseModel, Field

from palaver.app.agent_loop.call_counter import CallCounter
from palaver.app.dataclasses.message import ChatMessage, Message


class RunDeps(BaseModel):
    agent_id: str
    user_message: Message
    run_id: str
    call_counter: CallCounter
    agent_chain: tuple[str, ...] = Field(default_factory=tuple)
    chat_history: tuple[ChatMessage, ...] = Field(..., default_factory=tuple)
    awaited_by: str | None = None

    @property
    def sender(self):
        return self.user_message.sender
