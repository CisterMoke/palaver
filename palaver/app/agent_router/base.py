import abc

from collections.abc import Callable
from pydantic_ai.capabilities import AbstractCapability

from palaver.app.agent_loop.stream_session import StreamSession
from palaver.app.dataclasses.run_deps import RunDeps


class RouterPolicy(abc.ABC):

    def __init__(self, agent_id: str, other_agent_ids: list[str], stream_session: StreamSession):
        self.agent_id = agent_id
        self.other_agent_ids = other_agent_ids
        self.stream_session = stream_session

    @abc.abstractmethod
    def build_tools(self) -> list[Callable]:
        """Build tool functions available for the current run."""

    @abc.abstractmethod
    def build_capabilities(self, exclude_tools: bool = False) -> list[AbstractCapability[RunDeps]]:
        """Build pydantic-ai capabilities for the current run."""

    def edit_system_prompt(self, prompt: str) -> str:
        """Optionally append router-specific guidance to the prompt."""
        return prompt
