import uuid

from pydantic_ai.capabilities import Hooks
from pydantic_ai.messages import (
    AgentStreamEvent,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)
from pydantic_ai.tools import RunContext

from palaver.app.agent_loop.stream_session import StreamSession
from palaver.app.dataclasses.run_deps import RunDeps
from palaver.app.event_bridges.base import BaseEventBridge
from palaver.app.events.ui import AgentResponseChunkEvent, AgentResponseCompleteEvent, AgentResponseStartEvent


class UIEventBridge(BaseEventBridge):
    """Converts pydantic-ai stream/tool hooks into ui events."""

    def __init__(self, agent_id: str, stream_session: StreamSession):
        super().__init__(agent_id, stream_session)

        self._text_message_id: str | None = None

    async def handle_event(self, ctx: RunContext[RunDeps], event: AgentStreamEvent) -> AgentStreamEvent:
        if isinstance(event, PartStartEvent):
            await self._handle_part_start(ctx, event)
        elif isinstance(event, PartDeltaEvent):
            await self._handle_part_delta(ctx, event)
        elif isinstance(event, PartEndEvent):
            await self._handle_part_end(ctx, event)
        return event

    async def _handle_part_start(self, ctx: RunContext[RunDeps], event: PartStartEvent):
        part = event.part
        if isinstance(part, TextPart):
            self._text_message_id = str(uuid.uuid4())
            recipient = ctx.deps.sender
            await self._emit(
                AgentResponseStartEvent(
                    agent_id=self.agent_id,
                    message_id=self._text_message_id,
                    recipient=recipient,
                ),
            )
            if part.content:
                await self._emit(
                    AgentResponseChunkEvent(
                        agent_id=self.agent_id,
                        message_id=self._text_message_id,
                        delta=part.content,
                        recipient=recipient,
                    ),
                )

    async def _handle_part_delta(self, ctx: RunContext[RunDeps], event: PartDeltaEvent):
        delta = event.delta
        if isinstance(delta, TextPartDelta):
            if self._text_message_id is None:
                return
            await self._emit(
                AgentResponseChunkEvent(
                    agent_id=self.agent_id,
                    message_id=self._text_message_id,
                    delta=delta.content_delta,
                    recipient=ctx.deps.sender,
                ),
            )

    async def _handle_part_end(self, ctx: RunContext[RunDeps], event: PartEndEvent):
        part = event.part
        if isinstance(part, TextPart):
            if self._text_message_id is None:
                return
            await self._emit(
                AgentResponseCompleteEvent(
                    agent_id=self.agent_id,
                    message_id=self._text_message_id,
                    content=part.content,
                    recipient=ctx.deps.sender,
                ),
            )
            self._text_message_id = None

    
    def build_hooks(self) -> Hooks[RunDeps]:
        hooks = super().build_hooks()

        @hooks.on.event
        async def _on_event(ctx: RunContext[RunDeps], event: AgentStreamEvent) -> AgentStreamEvent:
            return await self.handle_event(ctx, event)
        return hooks

    
