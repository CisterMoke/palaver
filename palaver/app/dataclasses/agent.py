from enum import Enum
from pydantic import BaseModel

from palaver.app.config import AgentConfig, ProviderConfig
from palaver.app.dataclasses.message import Message

class MessageTarget(BaseModel):
    """Target for a message - can be specific agents or general"""
    agent_ids: list[str] | None = None  # Specific agent IDs
    is_general: bool = False  # General message flag
    
    def is_targeted(self) -> bool:
        """Check if message has specific targets"""
        return self.agent_ids is not None and len(self.agent_ids) > 0

class DelegationRequest(BaseModel):
    """Request for delegation between agents"""
    original_agent_id: str
    target_agent_ids: list[str]
    original_message: Message
    chat_history: list[Message]
    is_dependent: bool = False  # Whether original request depends on delegation result
    
class AgentAction(Enum):
    ACCEPT = "accept"
    DELEGATE = "delegate"

class AgentDecision(BaseModel):
    """Agent's decision on how to handle a message"""
    action: AgentAction
    delegation_request: DelegationRequest | None = None
    response: str | None = None

class AgentInfo(AgentConfig):
    id: str

    @classmethod
    def from_config(cls, config: AgentConfig) -> "AgentInfo":
        agent_id = config.name
        return cls(id=agent_id, **config.model_dump())

class AgentResponse(BaseModel):
    agent_id: str
    response: str
    timestamp: str
    error: str | None = None


class AddAgentRequest(BaseModel):
    agent_id: str


class CreateAgentRequest(AgentConfig):
    pass


class CreateProviderRequest(ProviderConfig):
    pass


class DeleteResponse(BaseModel):
    success: bool
    message: str
