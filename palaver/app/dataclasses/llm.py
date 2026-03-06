from pydantic import BaseModel, Field
from typing import Literal


class ChatroomMessage(BaseModel):
    """
    A message left in the chatroom.
    """
    sender: str = Field(..., description="The sender of the message.")
    role: Literal["agent", "user"] = Field(..., description="The role of the sender. Can be either 'agent' or 'user'.")
    content: str = Field(..., description="The content of the message.")


class AgentResponse(BaseModel):
    """
    The response of an AI Agent
    """
    class Reply(BaseModel):
        """
        A single reply of an AI Agent
        """
        content: str = Field(..., description="The content of the reply")
        recipient: str = Field("user", description="The recipient to which the reply is aimed to. Defaults to 'user'.")
        hand_off: bool = Field(False, description="Set to True if you fully hand off the task to the recipient and don't need to follow up on their answer. Defaults to False")
    replies: list[Reply]