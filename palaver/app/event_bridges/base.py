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

        # @hooks.on.node_run_error
        # async def _handle_error(
        #     ctx: RunContext[RunDeps],
        #     /,
        #     *,
        #     node: AgentNode,
        #     error: Exception
        # ) -> End:
        #     async with self.stream_session.get_stream() as stream:
        #         await stream.send(
        #             AgentResponseErrorEvent(
        #                 agent_id=self.agent_id,
        #                 error=str(error),
        #             )
        #         )
        #         return End(FinalResult(str(error)))

        # @hooks.on.after_run
        # async def _close_stream(ctx: RunContext[RunDeps], /, *, result: AgentRunResult) -> AgentRunResult:
        #     """Ensures self.send_stream is closed at the end of the run."""
        #     async with self.stream_session.get_stream():
        #         return result
        return hooks

