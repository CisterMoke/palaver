import anyio
import asyncio
import uuid

from collections.abc import Awaitable, AsyncIterator, AsyncGenerator
from contextlib import AbstractAsyncContextManager
from loguru import logger
from pydantic import BaseModel
from pydantic_core import from_json
from pydantic_ai import AgentRunResultEvent, AgentRunResult
from pydantic_ai.messages import (
    AgentStreamEvent, PartDeltaEvent, PartStartEvent, PartEndEvent,
    TextPart, TextPartDelta, ToolCallPartDelta, ToolCallPart, FunctionToolResultEvent,
)
from pydantic_ai.result import StreamedRunResult
from pydantic_ai.tools import RunContext

import palaver.app.dataclasses.events as ws_events

from palaver.app.constants import MAX_DEPTH_MESSAGE
from palaver.app.dataclasses.run_deps import RunDeps


class ToolInfo(BaseModel):
    message_id: str
    args_str: str = ""
    args_dict: dict = None  


class AgentRunWSStream:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.early_stop: bool = False

        self.message_id: str = ""
        self.tool_args = ""
        self.send_reply = None
        self.recipient = "USER"
        self.curr_tool_info: ToolInfo = None
        self.tool_info: dict[str, ToolInfo] = dict()

        self.send_stream, self.receive_stream = anyio.create_memory_object_stream[ws_events.WebSocketEvent]()
    
    def _handle_part_start_event(self, event: PartStartEvent):
        part = event.part
        logger.debug(f"{self.agent_id}: Event Start: {part}")
        if isinstance(part, TextPart):
            if self.send_reply == False: # noqa: E712
                self.early_stop = True
                return
            self.send_reply = False
            self.message_id = str(uuid.uuid4())
            yield ws_events.AgentResponseStartEvent(
                agent_id=self.agent_id, message_id=self.message_id,
                recipient=self.recipient
            )
            yield ws_events.AgentResponseChunkEvent(
                agent_id=self.agent_id, message_id=self.message_id, delta=part.content,
                recipient=self.recipient
            )
        elif isinstance(part, ToolCallPart) and part.tool_name == "message_agent":
            message_id=str(uuid.uuid4())
            self.tool_info[part.tool_call_id] = ToolInfo(message_id=message_id)
            self.curr_tool_info = self.tool_info[part.tool_call_id]
            args_str = self.curr_tool_info.args_str
            self.send_reply = False if self.send_reply is None else self.send_reply
            yield ws_events.AgentResponseStartEvent(
                agent_id=self.agent_id, message_id=message_id,
                recipient=self.recipient,
            )
            args_str = event.part.args_as_json_str()
            if not args_str:
                return
            tool_args_dict = from_json(args_str, allow_partial=True)
            if "content" in tool_args_dict:
                yield ws_events.AgentResponseChunkEvent(
                    agent_id=self.agent_id, message_id=message_id, delta=tool_args_dict["content"],
                    recipient=self.recipient,
                )

    def _handle_part_delta_event(self, event: PartDeltaEvent):
        delta = event.delta
        if isinstance(delta, TextPartDelta):
            yield ws_events.AgentResponseChunkEvent(
                agent_id=self.agent_id,
                message_id=self.message_id,
                delta=delta.content_delta,
                recipient=self.recipient
            )
        elif isinstance(event.delta, ToolCallPartDelta) and self.curr_tool_info == "message_agent":
            if not delta.args_delta:
                return
            args_str = self.curr_tool_info.args_str
            prev_tool_args_dict = from_json(args_str, allow_partial=True)
            args_str += delta.args_delta
            tool_args_dict = from_json(args_str, allow_partial=True)
            self.curr_tool_info.args_str = args_str
            if "content" not in tool_args_dict:
                return

            content_delta = tool_args_dict["content"][len(prev_tool_args_dict.get("content", "")):]
            yield ws_events.AgentResponseChunkEvent(
                agent_id=self.agent_id, message_id=self.curr_tool_info.message_id, delta=content_delta,
                recipient=self.recipient,
            )

    def _handle_part_end_event(self, event: PartEndEvent):
        part = event.part
        logger.debug(f"{self.agent_id}: Event End: {part}")
        store_message = True
        if isinstance(part, TextPart):
            content = part.content
        elif isinstance(part, ToolCallPart) and part.tool_name == "message_agent":
            args_dict = part.args_as_dict()
            content = args_dict["content"]
            self.curr_tool_info.args_dict = args_dict
            store_message=False
            self.curr_tool_info = None
        else:
            return
        yield ws_events.AgentResponseCompleteEvent(
            agent_id=self.agent_id, message_id=self.message_id, content=content,
            recipient=self.recipient, store_message=store_message
        )

    def _handle_event(self, event: AgentStreamEvent|AgentRunResultEvent):
        if isinstance(event, PartStartEvent):
            for result in self._handle_part_start_event(event):
                yield result 
        elif isinstance(event, PartDeltaEvent):
            for result in self._handle_part_delta_event(event):
                yield result
        elif isinstance(event, PartEndEvent):
            for result in self._handle_part_end_event(event):
                yield result
        elif isinstance(event, FunctionToolResultEvent):
            content = event.result.content
            logger.debug(f"{self.agent_id}: Function Tool Result: {content}")
            if event.result.tool_name == "message_agent":
                tool_info = self.tool_info[event.tool_call_id]
                message_id = tool_info.message_id
                if event.result.part_kind == "retry-prompt":
                    logger.debug(f"Redacting message from {self.agent_id}")
                    yield ws_events.RedactAgentResponseEvent(
                        agent_id=self.agent_id,
                        message_id=message_id
                    )
                else:
                    if (content == MAX_DEPTH_MESSAGE
                        or tool_info.args_dict["consume_reply"]
                    ):
                        self.send_reply = True
        else:
            logger.debug(f"{self.agent_id}: Received unhandled event '{event}'.")

    async def event_handler(self,
        ctx: RunContext[RunDeps],
        event_stream: AsyncIterator[AgentStreamEvent],
    ):
        async with ctx.deps.send_stream.clone() as stream:
            try:
                async for event in event_stream:
                    self.recipient = ctx.deps.recipient
                    if self.early_stop:
                        logger.debug(f"{self.agent_id}: Early stopping for agent")
                        break
                    for result in self._handle_event(event):
                        if isinstance(result, ws_events.AgentResponseCompleteEvent):
                            result.await_id_chain = ctx.deps.await_id_chain
                        await stream.send(result)

            except Exception as e:
                error_event = ws_events.AgentResponseErrorEvent(
                    agent_id=self.agent_id,
                    error=str(e),
                )
                await stream.send(error_event)
                raise e

    async def stream_ws_events(self, stream: AbstractAsyncContextManager[StreamedRunResult]) -> AsyncGenerator[ws_events.WebSocketEvent]:
        async def _consume_stream():    
            async with self.send_stream:
                async with stream as result:
                    if not self.early_stop:
                        async for event in result._stream_response:
                            for event in self._handle_event(event):
                                if self.early_stop:
                                    break
                                await self.send_stream.send(event)
                    await result._marked_completed()
                    

        loop = asyncio.get_event_loop()
        task = loop.create_task(_consume_stream())

        try:
            async with self.receive_stream:
                async for event in self.receive_stream:
                    yield event
            await task
        
        except Exception as e:
            yield ws_events.AgentResponseErrorEvent(
                agent_id=self.agent_id,
                error=str(e),
            )
            raise e

    async def stream_ws_events_run(self, run: Awaitable[AgentRunResult]) -> AsyncGenerator[ws_events.WebSocketEvent]:
        async def run_agent() -> AgentRunResult:    
            async with self.send_stream:
                return await run

        loop = asyncio.get_event_loop()
        task = loop.create_task(run_agent())

        try:
            async with self.receive_stream:
                async for event in self.receive_stream:
                    yield event
            await task
            logger.debug(f"{self.agent_id}: Finished awaiting task for agent")
        
        except Exception as e:
            yield ws_events.AgentResponseErrorEvent(
                agent_id=self.agent_id,
                error=str(e),
            )
            raise e


class RunEventWSStream:
    def __init__(self, stream: AsyncIterator[AgentStreamEvent|AgentRunResultEvent], agent_id: str):
        self.stream = stream
        self.agent_id = agent_id
        self.early_stop: bool = False

        self.message_id: str = ""
        self.tool_args = ""
        self.send_reply = None
        self.message_agent_tool_ids = []

    def _handle_part_start_event(self, event: PartStartEvent):
        part = event.part
        logger.debug(f"{self.agent_id}: Event Start: {part}")
        if isinstance(part, TextPart):
            if self.send_reply == False: # noqa: E712
                self.early_stop = True
                return
            self.send_reply = False
            self.message_id = str(uuid.uuid4())
            yield ws_events.AgentResponseStartEvent(
                agent_id=self.agent_id, message_id=self.message_id
            )
            yield ws_events.AgentResponseChunkEvent(
                agent_id=self.agent_id, message_id=self.message_id, delta=part.content
            )
        elif isinstance(part, ToolCallPart) and part.tool_name == "message_agent":
            self.message_id = str(uuid.uuid4())
            self.message_agent_tool_ids.append(part.tool_call_id)
            self.send_reply = False if self.send_reply is None else self.send_reply
            yield ws_events.AgentResponseStartEvent(
                agent_id=self.agent_id, message_id=self.message_id
            )
            self.tool_args = event.part.args_as_json_str()
            if not self.tool_args:
                return
            tool_args_dict = from_json(self.tool_args, allow_partial=True)
            if "content" in tool_args_dict:
                yield ws_events.AgentResponseChunkEvent(
                    agent_id=self.agent_id, message_id=self.message_id, delta=tool_args_dict["content"]
                )

    def _handle_part_delta_event(self, event: PartDeltaEvent):
        delta = event.delta
        if isinstance(delta, TextPartDelta):
            yield ws_events.AgentResponseChunkEvent(
                agent_id=self.agent_id,
                message_id=self.message_id,
                delta=delta.content_delta
            )
        elif isinstance(event.delta, ToolCallPartDelta):
            if not delta.args_delta:
                return
            prev_tool_args_dict = from_json(self.tool_args, allow_partial=True)
            self.tool_args += delta.args_delta
            tool_args_dict = from_json(self.tool_args, allow_partial=True)
            if "content" not in tool_args_dict:
                return

            content_delta = tool_args_dict["content"][len(prev_tool_args_dict.get("content", "")):]
            yield ws_events.AgentResponseChunkEvent(
                agent_id=self.agent_id, message_id=self.message_id, delta=content_delta
            )

    def _handle_part_end_event(self, event: PartEndEvent):
        part = event.part
        logger.debug(f"{self.agent_id}: Event End: {part}")
        if isinstance(part, TextPart):
            content = part.content
        elif isinstance(part, ToolCallPart):
            args_dict = part.args_as_dict()
            content=args_dict["content"]
            if args_dict.get("consume_reply", False):
                self.send_reply=True
        else:
            return
        yield ws_events.AgentResponseCompleteEvent(
            agent_id=self.agent_id, message_id=self.message_id, content=content
        )

    def _handle_event(self, event: AgentStreamEvent|AgentRunResultEvent):
        if isinstance(event, PartStartEvent):
            for result in self._handle_part_start_event(event):
                yield result 
        elif isinstance(event, PartDeltaEvent):
            for result in self._handle_part_delta_event(event):
                yield result
        elif isinstance(event, PartEndEvent):
            for result in self._handle_part_end_event(event):
                yield result
        elif isinstance(event, FunctionToolResultEvent) and event.tool_call_id in self.message_agent_tool_ids:
            content = event.result.content
            logger.debug(f"{self.agent_id}: Function Tool Result: {content}")
            self.send_reply = True if (content == MAX_DEPTH_MESSAGE) else self.send_reply

    async def stream_ws_events(self) -> AsyncGenerator[ws_events.WebSocketEvent]:
        try:
            async for event in self.stream:
                for result in self._handle_event(event):
                    yield result
                if self.early_stop:
                    break

        except Exception as e:
            yield ws_events.AgentResponseErrorEvent(
                agent_id=self.agent_id,
                error=str(e),
            )
            raise e

class OutputEventWSStream:
    def __init__(self, stream: StreamedRunResult, agent_id: str):
        self.stream = stream
        self.agent_id = agent_id

    async def stream_ws_events(self) -> AsyncGenerator[ws_events.WebSocketEvent]:
        async with self.stream as result:
            curr_idx = 0
            curr_content = ""
            message_id = str(uuid.uuid4())
            yield ws_events.AgentResponseStartEvent(
                agent_id=self.agent_id,
                message_id=message_id,
            )
            try:
                async for profile in result.stream_output():
                    logger.debug(profile)
                    if not profile.replies:
                        continue
                    curr_reply = profile.replies[curr_idx]

                    if not curr_reply.content:
                        continue

                    reply_content = curr_reply.content

                    if (len(profile.replies) > curr_idx - 1) and curr_content == reply_content:
                        yield ws_events.AgentResponseCompleteEvent(
                            agent_id=self.agent_id,
                            message_id=message_id,
                            content=curr_content,
                        )
                        message_id = str(uuid.uuid4())
                        curr_idx += 1
                        next_reply = profile.replies[curr_idx]
                        if not next_reply.content:
                            curr_content = ""
                        else:
                            curr_content = next_reply.content
                            yield ws_events.AgentResponseStartEvent(
                                agent_id=self.agent_id,
                                message_id=message_id
                            )

                        if curr_content:
                            yield ws_events.AgentResponseChunkEvent(
                                agent_id=self.agent_id,
                                message_id=message_id,
                                delta=curr_content,
                            )

                        continue

                    text_delta = reply_content[len(curr_content):len(reply_content)]
                    curr_content = reply_content

                    yield ws_events.AgentResponseChunkEvent(
                        agent_id=self.agent_id,
                        message_id=message_id,
                        delta=text_delta
                    )

                yield ws_events.AgentResponseCompleteEvent(
                    agent_id=self.agent_id,
                    message_id=message_id,
                    content=curr_content,
                )
            except Exception as e:
                yield ws_events.AgentResponseErrorEvent(
                    agent_id=self.agent_id,
                    error=str(e),
                )


class TextWSStream:
    def __init__(self, stream: StreamedRunResult, agent_id: str):
        self.stream = stream
        self.agent_id = agent_id

    async def stream_ws_events(self) -> AsyncGenerator[ws_events.WebSocketEvent]:
        message_id = str(uuid.uuid4())
        full_response = ""
        async with self.stream as result:
            yield ws_events.AgentResponseStartEvent(
                agent_id=self.agent_id, message_id=message_id,
            )
            try:
                async for delta in result.stream_text(delta=True):
                    yield ws_events.AgentResponseChunkEvent(
                        agent_id=self.agent_id, message_id=message_id, delta=delta
                    )
                    full_response += delta
                yield ws_events.AgentResponseCompleteEvent(
                    agent_id=self.agent_id, message_id=message_id, content=full_response
                )
            except Exception as e:
                yield ws_events.AgentResponseErrorEvent(
                    agent_id=self.agent_id,
                    error=str(e),
                )

