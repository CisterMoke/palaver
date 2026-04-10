from collections.abc import Callable
from pydantic_ai.capabilities import AbstractCapability

from palaver.app.agent_loop.stream_session import StreamSession
from palaver.app.agent_router.base import RouterPolicy
from palaver.app.dataclasses.run_deps import RunDeps


class SingleAgentRouterPolicy(RouterPolicy):
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
        return []