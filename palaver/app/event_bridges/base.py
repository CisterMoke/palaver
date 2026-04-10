import abc

from pydantic_ai import RunContext
from pydantic_ai.capabilities import Hooks
from pydantic_ai.messages import AgentStreamEvent

from palaver.app.agent_loop.stream_session import StreamSession
from palaver.app.dataclasses.run_deps import RunDeps


class BaseEventBridge(abc.ABC):
    def __init__(self, agent_id: str, stream_session: StreamSession):
        self.agent_id = agent_id
        self.stream_session = stream_session

    async def _emit(self, event) -> None:
        async with self.stream_session.get_stream() as stream:
            await stream.send(event)

    @abc.abstractmethod
    async def handle_event(self, ctx: RunContext[RunDeps], event: AgentStreamEvent) -> AgentStreamEvent:
        ...

    @abc.abstractmethod
    def build_hooks(self) -> Hooks[RunDeps]:
        hooks = Hooks[RunDeps]()
        return hooks

