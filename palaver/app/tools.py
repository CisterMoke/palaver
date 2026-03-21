import asyncio

from pydantic import BaseModel, Field
from pydantic_ai.tools import RunContext

from palaver.app.constants import MAX_DEPTH_MESSAGE
from palaver.app.dataclasses.message import Message
from palaver.app.enums import RoleEnum


class Metadata(BaseModel):
    chatroom_id: str
    agent_id: str
    chat_history: list = Field(..., default_factory=list)
    chain_depth: int = 1
    exceeds_max_depth: bool = False


def send_agent_tool(messaging_func, recipient_verifier):
    async def message_agent(ctx: RunContext[Metadata], recipient: str, content: str, await_reply: bool = False) -> str:
        """
        Send a message to an AI Agent.

        Args:
            recipient (str): The identifier of the AI Agent to send the message to.
            content (str): The content of the message to be sent.
            await_reply (bool, optional): If True, wait for and return the agent's reply. 
                                         If False, send the message asynchronously without waiting for a reply.
                                         Defaults to False.

        Returns:
            str: The reply from the AI Agent if await_reply is True. Otherwise, an empty string.

        Raises:
            ValueError: If the recipient agent is not found or is invalid.
        """
        if ctx.deps.exceeds_max_depth:
            return MAX_DEPTH_MESSAGE
        
        if not recipient_verifier(recipient):
            raise ValueError(f"Agent '{recipient}' not found.")
        
        message = Message(
            sender=ctx.deps.agent_id,
            role=RoleEnum.AGENT,
            content=content,
            target_agent_ids=[recipient]
        )
        loop = asyncio.get_event_loop()
        task = loop.create_task(messaging_func(
            chatroom_id=ctx.deps.chatroom_id,
            agent_id=recipient,
            user_message=message,
            chat_history=ctx.deps.chat_history,
            depth=ctx.deps.chain_depth + 1
        ))
        if not await_reply:
            return ""
        else:
            return await task
        
    return message_agent
