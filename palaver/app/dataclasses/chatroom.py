from pydantic import BaseModel


class ChatroomBase(BaseModel):
    name: str
    description: str | None = ""


class ChatroomCreate(ChatroomBase):
    pass


class Chatroom(ChatroomBase):
    id: str


class ChatroomWithAgents(Chatroom):
    agents: list[str] = []