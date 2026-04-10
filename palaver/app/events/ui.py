from pydantic import BaseModel

from palaver.app.dataclasses.message import ChatMessage


class UIEvent(BaseModel):
    type: str


class ChatMessageEvent(ChatMessage, UIEvent):
    """Event for a chat message"""
    type: str = "chat_message"


class UserLeftEvent(UIEvent):
    """Event for when a user leaves the chatroom"""
    type: str = "user_left"
    message: str


class BaseAgentResponseEvent(UIEvent):
    """Bese event for agent responses"""
    agent_id: str
    message_id: str


class AgentResponseStartEvent(BaseAgentResponseEvent):
    """Event for when an agent starts responding"""
    type: str = "agent_response_start"
    recipient: str | None = None


class AgentResponseChunkEvent(BaseAgentResponseEvent):
    """Event for streaming chunks of agent response"""
    type: str = "agent_response_chunk"
    delta: str
    recipient: str | None = None


class AgentResponseCompleteEvent(BaseAgentResponseEvent):
    """Event for when an agent completes its response"""
    type: str = "agent_response_complete"
    content: str
    recipient: str | None = None


class AgentResponseErrorEvent(UIEvent):
    """Event for when an agent response encounters an error"""
    type: str = "agent_response_error"
    agent_id: str
    error: str


class RedactAgentResponseEvent(BaseAgentResponseEvent):
    """Event for when an agent response must be redacted"""
    type: str = "redact_agent_response"