import uuid

from collections.abc import AsyncIterator, AsyncGenerator
from loguru import logger
from pydantic_core import from_json
from pydantic_ai import AgentRunResultEvent
from pydantic_ai.messages import (
    AgentStreamEvent, PartDeltaEvent, PartStartEvent, PartEndEvent,
    TextPart, TextPartDelta, ToolCallPartDelta, ToolCallPart, FunctionToolResultEvent
)

from pydantic_ai.result import StreamedRunResult

import palaver.app.dataclasses.events as ws_events

from palaver.app.constants import MAX_DEPTH_MESSAGE


class RunEventWSStream:
    def __init__(self, stream: AsyncIterator[AgentStreamEvent|AgentRunResultEvent], agent_id: str):
        self.stream = stream
        self.agent_id = agent_id

    async def stream_ws_events(self) -> AsyncGenerator[ws_events.WebSocketEvent]:
        tool_args = ""
        send_reply = None
        message_agent_tool_ids = []
        try:
            async for event in self.stream:
                if isinstance(event, PartStartEvent):
                    part = event.part
                    logger.debug(f"Event Start: {part}")
                    if isinstance(part, TextPart):
                        if send_reply == False: # noqa: E712
                            break
                        send_reply = False
                        message_id = str(uuid.uuid4())
                        yield ws_events.AgentResponseStartEvent(
                            agent_id=self.agent_id, message_id=message_id
                        )
                        yield ws_events.AgentResponseChunkEvent(
                            agent_id=self.agent_id, message_id=message_id, delta=part.content
                        )
                    elif isinstance(part, ToolCallPart) and part.tool_name == "message_agent":
                        message_id = str(uuid.uuid4())
                        message_agent_tool_ids.append(part.tool_call_id)
                        send_reply = False if send_reply is None else send_reply
                        yield ws_events.AgentResponseStartEvent(
                            agent_id=self.agent_id, message_id=message_id
                        )
                        tool_args = event.part.args_as_json_str()
                        if not tool_args:
                            continue
                        tool_args_dict = from_json(tool_args)
                        if "content" in tool_args_dict:
                            yield ws_events.AgentResponseChunkEvent(
                                agent_id=self.agent_id, message_id=message_id, delta=tool_args_dict["content"]
                            )
                elif isinstance(event, PartDeltaEvent):
                    delta = event.delta
                    if isinstance(delta, TextPartDelta):
                        yield ws_events.AgentResponseChunkEvent(
                            agent_id=self.agent_id,
                            message_id=message_id,
                            delta=delta.content_delta
                        )
                    elif isinstance(event.delta, ToolCallPartDelta):
                        if not delta.args_delta:
                            continue
                        prev_tool_args_dict = from_json(tool_args)
                        tool_args += delta.args_delta
                        tool_args_dict = from_json(tool_args)
                        if "content" not in tool_args_dict:
                            continue

                        content_delta = tool_args_dict["content"][len(prev_tool_args_dict.get("content", "")):]
                        yield ws_events.AgentResponseChunkEvent(
                            agent_id=self.agent_id, message_id=message_id, delta=content_delta
                        )
                elif isinstance(event, PartEndEvent):
                    part = event.part
                    logger.debug(f"Event End: {part}")
                    if isinstance(part, TextPart):
                        content = part.content
                    elif isinstance(part, ToolCallPart):
                        args_dict = part.args_as_dict()
                        content=args_dict["content"]
                        if args_dict.get("await_reply", False):
                            send_reply=True
                    else:
                        continue
                    yield ws_events.AgentResponseCompleteEvent(
                        agent_id=self.agent_id, message_id=message_id, content=content
                    )
                elif isinstance(event, FunctionToolResultEvent) and event.tool_call_id in message_agent_tool_ids:
                    send_reply = True if (event.content == MAX_DEPTH_MESSAGE) else send_reply
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

