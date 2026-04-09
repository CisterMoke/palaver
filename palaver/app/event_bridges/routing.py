from dataclasses import dataclass, field
import re
import uuid

from loguru import logger
from pydantic_ai.capabilities import Hooks, ValidatedToolArgs
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import (
    AgentStreamEvent,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    ToolCallPart,
    ToolCallPartDelta,
)
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_core import from_json
from typing import Iterator

from palaver.app.agent_loop.stream_session import StreamSession
from palaver.app.events.ui import (
    RedactAgentResponseEvent,
)
from palaver.app.exceptions import TerminateRun, TooManyCalls
from palaver.app.dataclasses.run_deps import RunDeps
from palaver.app.event_bridges.base import BaseEventBridge
from palaver.app.events.ui import AgentResponseChunkEvent, AgentResponseCompleteEvent, AgentResponseStartEvent


def normalize_recipient(recipient: str) -> str:
    if (match := re.search(r"AGENT \((.*?)\)", recipient)) is not None:
        match_value = match.group(1) or ""
        return match_value if match_value else recipient
    return recipient


@dataclass
class ToolCallState:
    message_id: str
    args_json: str = ""
    args_dict: dict = field(default_factory=dict)
    content_delta: str = ""
    error: str | None = None

    @property
    def content(self) -> str:
        value = self.args_dict.get("content")
        return value if isinstance(value, str) else ""

    @property
    def recipient(self) -> str:
        value = self.args_dict.get("recipient")
        return normalize_recipient(value) if isinstance(value, str) else ""
    
    @property
    def consume_reply(self) -> bool:
        value = self.args_dict.get("consume_reply", False)
        return value


class ToolCallTracker:
    """Tracks incremental message_agent tool-call args for token streaming."""
    def __init__(self):
        self._state_map: dict[str, ToolCallState] = {}

    @classmethod
    def _parse_args(cls, args_json: str) -> dict:
        if not args_json:
            return {}
        try:
            partial = from_json(args_json, allow_partial=True)
        except ValueError:
            partial = {}
        return partial

    @classmethod
    def _get_args(cls, part: ToolCallPart) -> tuple[str, dict]:
        args_json = part.args_as_json_str() or ""
        args_dict = cls._parse_args(args_json) if args_json else {}
        return args_json, args_dict

    @property
    def can_terminate(self) -> bool:
        for state in self._state_map.values():
            if state.consume_reply:
                return False
        return True and len(self._state_map) > 0
    
    @property
    def states(self) -> Iterator[ToolCallState]:
        return self._state_map.values()
    
    def get(self, tool_call_id: str) -> ToolCallState | None:
        return self._state_map.get(tool_call_id)
    
    # def pop(self, tool_call_id: str) -> ToolCallState | None:
    #     return self._state_map.pop(tool_call_id, None)

    def start(self, part: ToolCallPart) -> ToolCallState:
        state = ToolCallState(message_id=str(uuid.uuid4()))
        state.args_json, state.args_dict = self._get_args(part)
        self._state_map[part.tool_call_id] = state
        return state

    def update(self, delta: ToolCallPartDelta, tool_call_id: str) -> ToolCallState | None:
        state = self.get(tool_call_id)
        if state is None:
            return

        previous_content = state.content
        args_delta = delta.args_delta
        if isinstance(args_delta, str):
            if not delta.args_delta:
                return None
            state.args_json += args_delta
            state.args_dict = self._parse_args(state.args_json)
        elif isinstance(args_delta, dict):
            state.args_dict = state.args_dict | args_delta
        else:
            return None

        state.content_delta = state.content[len(previous_content):]
        if not state.content_delta:
            return None
        return state

    def finish(self, part: ToolCallPart) -> ToolCallState | None:
        state = self.get(part.tool_call_id)
        if state is None:
            return
        
        state.args_json, state.args_dict = self._get_args(part)
        return state


class AutonomousRouterBridge(BaseEventBridge):
    def __init__(
            self,
            agent_id: str,
            stream_session: StreamSession,
            other_agent_ids: list[str]
        ):
        super().__init__(agent_id, stream_session)
        self.other_agent_ids: list[str] = other_agent_ids
        self.tool_call_tracker = ToolCallTracker()
        self.terminate_run: TerminateRun | None = None

    async def handle_event(self, ctx: RunContext[RunDeps], event: AgentStreamEvent) -> AgentStreamEvent:
        if not isinstance(event, PartDeltaEvent):
            logger.debug(f"Handling event {event}")
        if isinstance(event, PartStartEvent):
            await self._handle_part_start(ctx, event)
        elif isinstance(event, PartDeltaEvent):
            await self._handle_part_delta(ctx, event)
        elif isinstance(event, PartEndEvent):
            await self._handle_part_end(ctx, event)
        if self.terminate_run is not None:
            logger.debug(f"Terminating run for agent '{ctx.deps.agent_id}' [{ctx.deps.run_id}]")
            raise self.terminate_run
        return event

    async def _handle_part_start(self, ctx: RunContext[RunDeps], event: PartStartEvent):
        part = event.part
        if not(isinstance(part, ToolCallPart) and part.tool_name == "message_agent"):
            if self.tool_call_tracker.can_terminate:
                final_output = "\n\n".join([state.content for state in self.tool_call_tracker.states])
                self.terminate_run = TerminateRun(final_output, f"Terminating run '{self.agent_id}'[{ctx.deps.run_id}]")
            return
        state = self.tool_call_tracker.start(part)
        
        try:
            ctx.deps.call_counter.add()
        except TooManyCalls as e:
            state.error = str(e)
            return
        
        recipient = state.recipient
        await self._emit(
            AgentResponseStartEvent(
                agent_id=self.agent_id,
                message_id=state.message_id,
                recipient=recipient,
            ),
        )

        if state.content:
            await self._emit(
                AgentResponseChunkEvent(
                    agent_id=self.agent_id,
                    message_id=state.message_id,
                    delta=state.content,
                    recipient=recipient,
                ),
            )
        return

    async def _handle_part_delta(self, ctx: RunContext[RunDeps], event: PartDeltaEvent):
        delta = event.delta
        if not isinstance(delta, ToolCallPartDelta):
            return 

        state = self.tool_call_tracker.update(delta, delta.tool_call_id)
        if state is not None and state.error is None and state.content_delta:
            await self._emit(
                AgentResponseChunkEvent(
                    agent_id=self.agent_id,
                    message_id=state.message_id,
                    delta=state.content_delta,
                    recipient=state.recipient,
                ),
            )

    async def _handle_part_end(self, ctx: RunContext[RunDeps], event: PartEndEvent):
        part = event.part
        if not(isinstance(part, ToolCallPart) and part.tool_name == "message_agent"):
            return

        state = self.tool_call_tracker.finish(part)
        if state is None or state.error is not None:
            return
        
        recipient = state.recipient
        if recipient == "USER":
            state.error = "Not allowed to send 'USER' a message with this tool!"
        elif recipient == self.agent_id:
            state.error = f"Cannot send message to self (you are '{recipient}')."
        elif recipient not in self.other_agent_ids:
            state.error = f"Agent '{recipient}' not found."

        if state.error is None:    
            await self._emit(
                AgentResponseCompleteEvent(
                    agent_id=self.agent_id,
                    message_id=state.message_id,
                    content=state.content,
                    recipient=state.recipient,
                ),
            )
        else: 
            await self._emit(
                RedactAgentResponseEvent(
                    agent_id=self.agent_id,
                    message_id=state.message_id,
                ),
            )

    # async def _handle_final_result(self, ctx: RunContext[RunDeps], event: FinalResultEvent):
    #     if not self.tool_call_tracker.has_awaiting:
    #         self.terminate_run = True
    #         self.final_output = "\n\n".join([state.content for state in self.tool_call_tracker.states])

    # async def _handle_tool_result_event(
    #     self, ctx: RunContext[RunDeps], event: FunctionToolResultEvent
    # ):
    #     result = event.result
    #     if result.tool_name != "message_agent":
    #         return
        
    #     state = self.tool_call_tracker.pop(result.tool_call_id)
    #     if state is None:
    #         return
        
    #     if result.part_kind == "retry-prompt":
    #         await self._emit(
    #             RedactAgentResponseEvent(
    #                 agent_id=self.agent_id,
    #                 message_id=state.message_id,
    #             ),
    #         )
    #     else:
    #         await self._emit(
    #             AgentResponseCompleteEvent(
    #                 agent_id=self.agent_id,
    #                 message_id=state.message_id,
    #                 content=state.content,
    #                 recipient=state.recipient,
    #             ),
    #         )
    #         if not state.consume_reply:
    #             self.final_output = result

    def build_hooks(self) -> Hooks[RunDeps]:
        hooks = super().build_hooks()

        @hooks.on.event
        async def _on_event(ctx: RunContext[RunDeps], event: AgentStreamEvent) -> AgentStreamEvent:
            return await self.handle_event(ctx, event)
        
        @hooks.on.before_tool_validate
        async def _raise_model_retry(
            ctx: RunContext[RunDeps],
            /,
            *, 
            call: ToolCallPart,
            tool_def: ToolDefinition,
            args: ValidatedToolArgs
        ) -> ValidatedToolArgs:
            state = self.tool_call_tracker.get(call.tool_call_id)
            if state.error is not None:
                raise ModelRetry(state.error)
            return args
        return hooks
        
        # @hooks.on.node_run_error
        # async def _gracefully_terminate(
        #     ctx: RunContext[RunDeps],
        #     /,
        #     *,
        #     node: AgentNode,
        #     error: Exception
        # ) -> End:
        #     logger.debug(f"Handling error {error}")
        #     if isinstance(error, TerminateRun):
        #         return End(FinalResult(error.output))
        #     return node
        # return hooks

        # @hooks.on.after_tool_execute(tools=["message_agent"])
        # async def _after_tool_execute(
        #     ctx: RunContext[RunDeps],
        #     /,
        #     *,
        #     call: ToolCallPart,
        #     tool_def: ToolDefinition,
        #     args: ValidatedToolArgs,
        #     result,
        # ):
        #     state = self._tracker.get(call.tool_call_id)
        #     if state is not None:
        #         await self._emit(
        #             ctx,
        #             AgentResponseCompleteEvent(
        #                 agent_id=self.agent_id,
        #                 message_id=state.message_id,
        #                 content=state.content,
        #                 recipient=state.recipient,
        #                 store_message=True,
        #             ),
        #         )
        #     return result

        # @hooks.on.tool_execute_error(tools=["message_agent"])
        # async def _tool_execute_error(
        #     ctx: RunContext[RunDeps],
        #     *,
        #     call: ToolCallPart,
        #     error: Exception,
        #     **_,
        # ):
        #     state = self._tracker.get(call.tool_call_id)
        #     if state is not None:
        #         await self._emit(
        #             ctx,
        #             RedactAgentResponseEvent(
        #                 agent_id=self.agent_id,
        #                 message_id=state.message_id,
        #             ),
        #         )
        #     raise error

        # return hooks

