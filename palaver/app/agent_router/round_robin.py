import random
import uuid

from collections.abc import Callable
from pydantic_ai import RunContext, AgentRunResult
from pydantic_ai.capabilities import AbstractCapability, Hooks

from palaver.app.agent_loop.stream_session import StreamSession
from palaver.app.agent_router.base import RouterPolicy
from palaver.app.dataclasses.run_deps import RunDeps
from palaver.app.dataclasses.message import Message, ChatMessage
from palaver.app.enums import RoleEnum
from palaver.app.events.agent import SendAgentEvent
from palaver.app.exceptions import TooManyCalls


class RoundRobinRouterPolicy(RouterPolicy):
    def __init__(
            self,
            active_agent_id: str,
            available_agent_ids: list[str],
            parent_agent_ids: tuple[str, ...],
            stream_session: StreamSession
        ):
        super().__init__(active_agent_id, available_agent_ids, parent_agent_ids, stream_session)

    def allowed_agent_ids(self) -> list[str]:
        exclude_agents = self.parent_agent_ids + (self.active_agent_id,)
        return [aid for aid in self.available_agent_ids if aid not in exclude_agents]
    
    def build_tools(self)-> list[Callable]:
        return []

    def build_capabilities(self, exclude_tools: bool = False) -> list[AbstractCapability[RunDeps]]:
        hooks = Hooks[RunDeps]()

        @hooks.on.after_run
        async def create_send_agent_event(ctx: RunContext[RunDeps], /, *, result: AgentRunResult) -> AgentRunResult:
            if not (allowed_agents := self.allowed_agent_ids()):
                return result
            
            run_deps = ctx.deps
            try:
                run_deps.call_counter.add()
            except TooManyCalls:
                return result
            
            next_agent = random.choice(allowed_agents)
            message = Message(
                sender=run_deps.agent_id,
                role=RoleEnum.AGENT,
                content=result.output,
            )
            user_chat_message = ChatMessage( # TODO: fix me. Use regular Message instead
                **run_deps.user_message.model_dump(),
                id="inner_chain_id",
                chatroom_id="inner_chain_id",
                timestamp="",
            )
            async with self.stream_session.get_stream() as stream:
                send_event = SendAgentEvent(
                    recipient=next_agent,
                    message=message,
                    chat_history=list(run_deps.chat_history) + [user_chat_message],
                    run_id=str(uuid.uuid4()),
                    agent_chain=run_deps.agent_chain + (run_deps.agent_id,),
                    awaited_by=run_deps.awaited_by,
                )
                await stream.send(send_event)
            return result

        return [hooks]