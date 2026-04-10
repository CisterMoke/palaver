import abc

from collections.abc import Callable
from pydantic_ai.capabilities import AbstractCapability

from palaver.app.agent_loop.stream_session import StreamSession
from palaver.app.dataclasses.run_deps import RunDeps


class RouterPolicy(abc.ABC):

    def __init__(
            self,
            active_agent_id: str,
            available_agent_ids: list[str],
            parent_agent_ids: tuple[str, ...],
            stream_session: StreamSession
        ):
        self.active_agent_id = active_agent_id
        self.available_agent_ids = available_agent_ids
        self.parent_agent_ids = parent_agent_ids
        self.stream_session = stream_session

    @abc.abstractmethod
    def allowed_agent_ids(self) -> list[str]:
        """Return a list of allowed agent ids that can be messaged."""

    @abc.abstractmethod
    def build_tools(self) -> list[Callable]:
        """Build tool functions available for the current run."""

    @abc.abstractmethod
    def build_capabilities(self, exclude_tools: bool = False) -> list[AbstractCapability[RunDeps]]:
        """Build pydantic-ai capabilities for the current run."""

    def edit_system_prompt(self, prompt: str) -> str:
        """Optionally append router-specific guidance to the prompt."""
        return prompt
