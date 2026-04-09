import pytest

from pydantic_ai.messages import ToolCallPart, ToolCallPartDelta

from palaver.app.events.agent import (
    AgentFinishedEvent,
)
from palaver.app.events.agent import SendAgentEvent
from palaver.app.events.ui import AgentResponseCompleteEvent
from palaver.app.event_handlers.core import AwaitTracker
from palaver.app.event_bridges.ui import MessageAgentStreamTracker


async def _noop():
    return None


def test_message_agent_stream_tracker_parses_partial_content_delta():
    tracker = MessageAgentStreamTracker()
    part = ToolCallPart(
        tool_name="message_agent",
        args='{"recipient":"AgentB","content":"Hel',
        tool_call_id="call-1",
    )
    state = tracker.start(call=part, part_index=0)

    assert state.content == "Hel"
    assert state.recipient == "AgentB"

    update = tracker.update(
        delta=ToolCallPartDelta(args_delta='lo world"}'),
        part_index=0,
    )

    assert update is not None
    updated_state, content_delta = update
    assert updated_state.message_id == state.message_id
    assert content_delta == "lo world"


@pytest.mark.asyncio
async def test_await_tracker_resolves_consumed_chain_after_all_finishes():
    tracker = AwaitTracker()
    root_event = SendAgentEvent(_noop(), await_id_chain=("root",), is_awaited=True)
    tracker.register_send_event(root_event)

    # Non-awaited descendant increases await counter for the awaited root chain.
    child_event = SendAgentEvent(_noop(), await_id_chain=("root",), is_awaited=False)
    tracker.register_send_event(child_event)

    tracker.collect_reply(
        AgentResponseCompleteEvent(
            agent_id="AgentA",
            message_id="m-1",
            content="Partial reply",
            recipient="USER",
            await_id_chain=("root",),
        )
    )

    # First finish decrements counter, second resolves the consumed result.
    tracker.handle_agent_finished(AgentFinishedEvent(("root",)))
    tracker.handle_agent_finished(AgentFinishedEvent(("root",)))

    assert await root_event.get_result() == "AgentA: Partial reply"
    root_event._coro.close()
    child_event._coro.close()
