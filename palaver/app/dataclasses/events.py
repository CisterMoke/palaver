import asyncio

from pydantic import BaseModel, Field

from palaver.app.dataclasses.message import ChatMessage


class CoroEvent:
    def __init__(self, coro):
        self._coro = coro
        self._done = asyncio.Event()
        self._result = None

    def __await__(self):
        yield from self._coro.__await__()

    async def __call__(self):
        return await self

    def set_result(self, value):
        self._done.set()
        self._result = value

    async def get_result(self):
        await self._done.wait()
        return self._result
    

class SendAgentEvent(CoroEvent):
    def __init__(self, coro, await_id_chain: tuple[str, ...], is_awaited: bool = False):
        super().__init__(coro)
        self.await_id_chain = await_id_chain
        self.is_awaited = is_awaited


class AgentFinishedEvent:
    def __init__(self, await_id_chain: tuple[str, ...]):
        self.await_id_chain = await_id_chain


class WebSocketEvent(BaseModel):
    type: str


class ChatMessageEvent(ChatMessage, WebSocketEvent):
    """Event for a chat message"""
    type: str = "chat_message"


class UserLeftEvent(WebSocketEvent):
    """Event for when a user leaves the chatroom"""
    type: str = "user_left"
    message: str


class BaseAgentResponseEvent(WebSocketEvent):
    """Bese event for agent responses"""
    agent_id: str
    message_id: str


class AgentResponseStartEvent(BaseAgentResponseEvent):
    """Event for when an agent starts responding"""
    type: str = "agent_response_start"
    recipient: str


class AgentResponseChunkEvent(BaseAgentResponseEvent):
    """Event for streaming chunks of agent response"""
    type: str = "agent_response_chunk"
    delta: str
    recipient: str


class AgentResponseCompleteEvent(BaseAgentResponseEvent):
    """Event for when an agent completes its response"""
    type: str = "agent_response_complete"
    content: str
    recipient: str
    store_message: bool
    await_id_chain: tuple[str, ...] = Field(..., default_factory=tuple)


class AgentResponseErrorEvent(WebSocketEvent):
    """Event for when an agent response encounters an error"""
    type: str = "agent_response_error"
    agent_id: str
    error: str


class RedactAgentResponseEvent(BaseAgentResponseEvent):
    """Event for when an agent response must be redacted"""
    type: str = "redact_agent_response"


Event = AgentFinishedEvent | CoroEvent | WebSocketEvent