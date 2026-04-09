import uuid

from collections.abc import Callable
from pydantic_ai import RunContext
from pydantic_ai.capabilities import AbstractCapability, Toolset
from pydantic_ai.toolsets import FunctionToolset

from palaver.app.agent_loop.stream_session import StreamSession
from palaver.app.agent_router.base import RouterPolicy
from palaver.app.dataclasses.run_deps import RunDeps
from palaver.app.dataclasses.message import Message, ChatMessage
from palaver.app.enums import RoleEnum
from palaver.app.event_bridges.routing import AutonomousRouterBridge, normalize_recipient
from palaver.app.events.agent import AwaitAgentEvent, SendAgentEvent


class AutonomousRouterPolicy(RouterPolicy):
    prompt_appendix: str = """
# ADDITIONAL INFO
Messaging other agents must be done via the provided "message_agent" tool.
You are only allowed to message the following agents:
[[other_agents]]
"""
    def __init__(self, agent_id: str, other_agent_ids: list[str], stream_session: StreamSession):
        super().__init__(agent_id, other_agent_ids, stream_session)

    def build_tools(self) -> list[Callable]:
        if not self.other_agent_ids:
            return []
        
        async def message_agent(
            ctx: RunContext[RunDeps], recipient: str, content: str, consume_reply: bool
        ) -> str:
            """
            Send a message to an AI agent to delegate a task and optionally receive/consume the reply with "consume_reply".
            The message content must be directed towards the recipient and the recipient only. Do not address multiple agents or users in your message content.
            You can only receive the content of the agent's reply if you consume it.
            Consumed replies are not sent to upstream agents so make sure your final response is self-contained.

            Args:
                recipient (str): The name of the AI Agent to send the message to. The recipient CANNOT be yourself or "USER".
                content (str): The content of the message to be sent. Do not address multiple agents or users in your content.
                consume_reply (bool): If True, the agent's reply is consumed and not sent to upstream agents.
                    If False, the message is sent asynchronously and not consumed.

            Returns:
                str: The reply from the AI Agent if await_reply is True. Otherwise, a default message.
            """
            run_deps = ctx.deps
            recipient = normalize_recipient(recipient)
            message = Message(
                sender=ctx.deps.agent_id,
                role=RoleEnum.AGENT,
                content=content,
                recipients=[recipient],
            )
            user_chat_message = ChatMessage( # TODO: fix me. Use regular Message instead
                **run_deps.user_message.model_dump(),
                id="inner_chain_id",
                chatroom_id="inner_chain_id",
                timestamp="",
            )
            async with self.stream_session.get_stream() as stream:
                if consume_reply:
                    await_event = AwaitAgentEvent(run_deps.run_id)
                    await stream.send(await_event)

                awaited_by = run_deps.run_id if consume_reply else run_deps.awaited_by
                send_event = SendAgentEvent(
                    recipient=recipient,
                    message=message,
                    chat_history=list(run_deps.chat_history) + [user_chat_message],
                    run_id=str(uuid.uuid4()),
                    agent_chain=run_deps.agent_chain + (run_deps.agent_id,),
                    awaited_by=awaited_by,
                )
                await stream.send(send_event)
                return await await_event if consume_reply else "Reply not consumed"

        return [message_agent]

    def build_capabilities(self, exclude_tools: bool = False) -> list[AbstractCapability[RunDeps]]:
        bridge = AutonomousRouterBridge(
            agent_id=self.agent_id,
            stream_session=self.stream_session,
            other_agent_ids=self.other_agent_ids,
        )
        hooks = bridge.build_hooks()

        if exclude_tools:
            return [hooks]
        
        toolset = Toolset(FunctionToolset(self.build_tools()))
        return [hooks, toolset]

    def edit_system_prompt(self, prompt: str) -> str:
        other_agent_list = "\n".join(self.other_agent_ids)
        prompt_appendix = self.prompt_appendix.replace("[[other_agents]]", other_agent_list)
        prompt = f"{prompt.strip()}\n{prompt_appendix}"
        return prompt
