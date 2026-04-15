import abc

from collections.abc import Callable
from pydantic_ai.capabilities import AbstractCapability, Hooks

from palaver.app.agent_loop.stream_session import StreamSession
from palaver.app.dataclasses.agent import AgentInfo
from palaver.app.dataclasses.run_deps import RunDeps
from palaver.app.prompts import BASE_PROMPT


class RouterPolicy(abc.ABC):
    def __init__(
            self,
            active_agent_id: str,
            available_agent_ids: list[str],
            parent_agent_ids: tuple[str, ...],
            agent_infos: dict[str, AgentInfo],
            stream_session: StreamSession,
        ):
        self.active_agent_id = active_agent_id
        self.available_agent_ids = available_agent_ids
        self.parent_agent_ids = parent_agent_ids
        self.agent_infos = agent_infos
        self.stream_session = stream_session

    @abc.abstractmethod
    def allowed_agent_ids(self) -> list[str]:
        """Return a list of allowed agent ids that can be messaged."""

    @abc.abstractmethod
    def build_tools(self) -> list[Callable]:
        """Build tool functions available for the current run."""

    @abc.abstractmethod
    def build_hooks(self) -> list[Hooks[RunDeps]]:
        """Build pydantic-ai hooks available for the current run."""

    @abc.abstractmethod
    def build_capabilities(self, exclude_tools: bool = False) -> list[AbstractCapability[RunDeps]]:
        """Build pydantic-ai capabilities for the current run."""

    def create_system_prompt(self) -> str:
        """Build the system prompt"""
        agent = self.agent_infos[self.active_agent_id]
        other_agents: list[AgentInfo] = []
        for aid in self.allowed_agent_ids():
            if (other_agent := self.agent_infos[aid]) is not None:
                other_agents.append(other_agent)

        other_agent_descriptions = "\n".join(
            [f"- AGENT ({agent.name}): {agent.description}" for agent in other_agents]
        )
        prompt = (
            BASE_PROMPT.replace("[[agent_name]]", agent.name)
            .replace("[[agent_description]]", agent.description)
            .replace("[[other_agent_descriptions]]", other_agent_descriptions)
            .replace("[[agent_prompt]]", agent.prompt)
        )
        return prompt