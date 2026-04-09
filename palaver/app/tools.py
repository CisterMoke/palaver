import re
import uuid

from collections.abc import Callable
from typing import cast
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.tools import RunContext

from palaver.app.constants import MAX_DEPTH_MESSAGE
from palaver.app.events.agent import SendAgentEvent
from palaver.app.dataclasses.message import Message, ChatMessage
from palaver.app.dataclasses.run_deps import RunDeps
from palaver.app.enums import RoleEnum


def set_recipient_tool(agent_ids: list[str]):
    async def set_recipient(ctx: RunContext[RunDeps], recipient: str) -> str:
        """
        Set the recipient to whom your next message will be sent. The recipient is set to "USER" by default.

        Args:
            recipient (str): The identifier of the AI Agent or "USER" to send the message to.

        Returns:
            str: A confirmation message
        """
        if recipient not in agent_ids + ["USER"]:
            raise ModelRetry(f"Recipient '{recipient}' not found.")

        run_deps = ctx.deps
        run_deps.sender = recipient

        return f"Recipient is now set to '{recipient}'"

    return set_recipient


def _normalize_recipient(recipient: str) -> str:
    if (match := re.search(r"AGENT \((.*?)\)", recipient)) is not None:
        match_value = match.group(1) or ""
        return str(match_value) if match_value else recipient
    return recipient


def build_delegate_to_agent_tool(
    message_agent_event_func: Callable[..., SendAgentEvent],
    recipient_verifier: Callable[[str], bool],
    route_state_updater: Callable,
):
    async def message_agent(
        ctx: RunContext[RunDeps], recipient: str, content: str, consume_reply: bool
    ) -> str:
        """
        Send a message to an AI agent to delegate a task and optionally receive/consume the reply with "consume_reply".
        You can only receive the content of the reply if you cosume it.
        Consumed replies are not sent to upstream agents so make sure your final response is self-contained.

        Args:
            recipient (str): The name of the AI Agent to send the message to. The recipient CANNOT be yourself or "USER".
            content (str): The content of the message to be sent.
            consume_reply (bool): If True, the agent's reply is consumed and not sent to upstream agents.
                If False, the message is sent asynchronously and not consumed.

        Returns:
            str: The reply from the AI Agent if await_reply is True. Otherwise, a default message.
        """
        run_deps = ctx.deps
        if (
            run_deps.max_subagent_calls is not None
            and run_deps.call_counter >= run_deps.max_subagent_calls
        ):
            return MAX_DEPTH_MESSAGE

        recipient = _normalize_recipient(recipient)

        if recipient == "USER":
            raise ModelRetry("Not allowed to send 'USER' a message with this tool!")
        elif recipient == run_deps.agent_id:
            raise ModelRetry(f"Cannot send message to self (you are '{recipient}').")
        if not recipient_verifier(recipient):
            raise ModelRetry(f"Agent '{recipient}' not found.")

        message = Message(
            sender=ctx.deps.agent_id,
            role=RoleEnum.AGENT,
            content=content,
            recipients=[recipient],
        )
        user_chat_message = ChatMessage(
            **run_deps.user_message.model_dump(),
            id="inner_chain_message",
            chatroom_id=run_deps.chatroom_id,
            timestamp="",
        )
        route_state = route_state_updater(
            run_deps.route_state,
            recipient,
        )
        new_run_deps = RunDeps(
            chatroom_id=run_deps.chatroom_id,
            agent_id=recipient,
            user_message=message,
            route_state=route_state,
            send_stream=run_deps.send_stream.clone(),
            chat_history=run_deps.chat_history + (user_chat_message,),
            max_subagent_calls=run_deps.max_subagent_calls,
            sender=run_deps.sender,
            call_counter=run_deps.call_counter,
            await_id_chain=run_deps.await_id_chain + (str(uuid.uuid4()),)
            if consume_reply
            else run_deps.await_id_chain,
        )
        new_run_deps.call_counter.add()
        event = message_agent_event_func(
            run_deps=new_run_deps, await_reply=consume_reply
        )
        async with run_deps.send_stream.clone() as stream:
            await stream.send(event)
        if consume_reply:
            result = await event.get_result()
            return cast(str, result) if isinstance(result, str) else ""
        return "Reply not consumed"

    return message_agent


send_agent_tool = build_delegate_to_agent_tool
