from loguru import logger
from pydantic_ai import RunContext, AgentRunResult
from pydantic_ai.capabilities import Hooks
from pydantic_ai.messages import AgentStreamEvent

from palaver.app.dataclasses.run_deps import RunDeps
from palaver.app.event_bridges.base import BaseEventBridge
from palaver.app.events.agent import AgentFinishedEvent
from palaver.app.exceptions import TerminateRun


class CoreEventBridge(BaseEventBridge):
    async def send_finished_event(self, run_deps: RunDeps, result: AgentRunResult):
        async with self.stream_session.get_stream() as stream:
            result_event = AgentFinishedEvent(
                run_id=run_deps.run_id,
                awaited_by=run_deps.awaited_by,
                result=result.output
            )
            await stream.send(result_event)

    async def handle_event(self, ctx: RunContext[RunDeps], event: AgentStreamEvent) -> AgentStreamEvent:
        return event

    def build_hooks(self) -> Hooks[RunDeps]:
        hooks = Hooks[RunDeps]()

        @hooks.on.event
        async def _on_event(ctx: RunContext[RunDeps], event: AgentStreamEvent) -> AgentStreamEvent:
            return await self.handle_event(ctx, event)

        @hooks.on.run_error
        async def _handle_run_error(
            ctx: RunContext[RunDeps],
            error: BaseException,
        ) -> AgentRunResult:
            if not isinstance(error, TerminateRun):
                raise error
            result = AgentRunResult(output=error.output)
            return result
        
        @hooks.on.after_run
        async def _finish_run(ctx: RunContext[RunDeps], /, *, result: AgentRunResult) -> AgentRunResult:
            logger.debug(
                f"Finished Agent Run {ctx.deps.run_id}, awaited_by={ctx.deps.awaited_by}."
            )
            await self.send_finished_event(ctx.deps, result)
            return result

        return hooks