from pydantic import BaseModel

from palaver.app.dataclasses.message import ChatMessage
from palaver.app.events.base import Event


class UIEvent(BaseModel, Event):
    type: str


class ChatMessageEvent(ChatMessage, UIEvent):
    """Event for a chat message"""

    type: str = "chat_message"


class SystemMessageEvent(UIEvent):
    """Event for a system message"""
    type: str = "system_message"
    message: str


class AgentLeftEvent(SystemMessageEvent):
    """Event for when an agent leaves the chatroom"""

    sub_type: str = "agent_left"
    agent_id: str


class BaseAgentResponseEvent(UIEvent):
    """Base event for agent responses"""

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


class CommandResultEvent(UIEvent):
    """Event for slash command execution result"""

    type: str = "command_result"
    name: str
    status: str
    payload: dict | None = None
    error: str | None = None


class AgentLoopStartEvent(UIEvent):
    """Event indicating the agent loop has started"""
    type: str = "agent_loop_start"


class AgentLoopEndEvent(UIEvent):
    """Event indicating the agent loop has ended"""
    type: str = "agent_loop_end"


class AgentStartEvent(UIEvent):
    """Event indicating the agent has started"""
    type: str = "agent_start_event"
    agent_id: str


class AgentEndEvent(UIEvent):
    """Event indicating the agent has ended"""
    type: str = "agent_end_event"
    agent_id: str
