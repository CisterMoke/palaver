import re
import uuid

from collections.abc import Callable
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.tools import RunContext

from palaver.app.agent_router.deterministic import DeterministicRouter
from palaver.app.constants import MAX_DEPTH_MESSAGE
from palaver.app.dataclasses.events import SendAgentEvent, AgentResponseCompleteEvent
from palaver.app.dataclasses.message import Message, ChatMessage
from palaver.app.dataclasses.run_deps import RunDeps
from palaver.app.enums import RoleEnum
from palaver.app.ws_event_stream import AgentRunWSStream


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
        run_deps.recipient = recipient

        return f"Recipient is now set to '{recipient}'"
    return set_recipient


def send_agent_tool(
        message_agent_event_func: Callable[..., SendAgentEvent],
        recipient_verifier: Callable[[str], bool],
        event_stream_handler: AgentRunWSStream,
    ):
    async def message_agent(ctx: RunContext[RunDeps], recipient: str, content: str, consume_reply: bool) -> str:
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
        if run_deps.max_subagent_calls is not None and run_deps.call_counter >= run_deps.max_subagent_calls:
            return MAX_DEPTH_MESSAGE
        
        if (match := re.search(r"AGENT \((.*?)\)", recipient)) is not None:
            recipient = match.group(1)
        
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
            target_agent_ids=[recipient]
        )
        user_chat_message = ChatMessage(
            **run_deps.user_message.model_dump(),
            id="inner_chain_message",
            chatroom_id=run_deps.chatroom_id,
            timestamp=""
        )
        route_state = DeterministicRouter.update_state(
            run_deps.route_state, recipient,
        )
        new_run_deps = RunDeps(
            agent_id=recipient,
            user_message=message,
            route_state=route_state,
            send_stream=run_deps.send_stream.clone(),
            chat_history=run_deps.chat_history + (user_chat_message,),
            call_counter=run_deps.call_counter,
            await_id_chain= run_deps.await_id_chain + (str(uuid.uuid4()),) if consume_reply else run_deps.await_id_chain,
            **run_deps.model_dump(include={"chatroom_id", "max_subagent_calls", "recipient"}),
        )
        new_run_deps.call_counter.add()
        event = message_agent_event_func(
            run_deps=new_run_deps,
            await_reply=consume_reply
        )
        async with run_deps.send_stream.clone() as stream:
            tool_info = event_stream_handler.tool_info[ctx.tool_call_id]
            save_message_event = AgentResponseCompleteEvent(
                agent_id=run_deps.agent_id, message_id=tool_info.message_id,
                content=tool_info.args_dict["content"],
                recipient=recipient, store_message=True,
            )
            await stream.send(save_message_event)
            await stream.send(event)
        if consume_reply:
            return await event.get_result()
        return "Reply not consumed"
        
    return message_agent
