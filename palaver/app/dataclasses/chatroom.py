import datetime as dt
import uuid

from pydantic import BaseModel, Field


from palaver.app.enums import RoutingType


def _create_uuid() -> str:
    return str(uuid.uuid4())


def _create_timestamp() -> str:
    return dt.datetime.now().isoformat()


class ChatroomBase(BaseModel):
    name: str
    limit_subagent_calls: bool = True
    max_subagent_calls: int = 3
    max_message_history: int = 20
    routing_type: RoutingType = RoutingType.AUTONOMOUS


class ChatroomCreate(ChatroomBase):
    pass


class ChatroomUpdate(ChatroomBase):
    name: str | None = None
    limit_agent_chains: bool | None = None
    max_chain_depth: int | None = None
    max_message_history: int | None = None


class Chatroom(ChatroomBase):
    chatroom_id: str = Field(alias="id", default_factory=_create_uuid)
    agents: list[str] = []
    created_at: str = Field(default_factory=_create_timestamp)