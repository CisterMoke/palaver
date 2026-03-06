from pydantic import BaseModel

from palaver.app.dataclasses.message import ChatMessage


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


class AgentResponseChunkEvent(BaseAgentResponseEvent):
    """Event for streaming chunks of agent response"""
    type: str = "agent_response_chunk"
    delta: str


class AgentResponseCompleteEvent(BaseAgentResponseEvent):
    """Event for when an agent completes its response"""
    type: str = "agent_response_complete"
    content: str


class AgentResponseErrorEvent(WebSocketEvent):
    """Event for when an agent response encounters an error"""
    type: str = "agent_response_error"
    agent_id: str
    error: str