from collections.abc import AsyncGenerator
from datetime import datetime
from functools import lru_cache
from loguru import logger
from typing import Any, Literal

from pydantic_ai import FunctionToolset
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    SystemPromptPart,
)

from palaver.app.config import AgentConfig, LLMConfig, ProviderConfig
from palaver.app.dataclasses.agent import (
    AgentInfo,
    AgentResponse,
    MessageTarget,
)
from palaver.app.dataclasses.llm import ChatroomMessage
from palaver.app.dataclasses.message import Message
from palaver.app.enums import RoleEnum
from palaver.app.models.agent import Agent, ProviderModels
from palaver.app.prompts import BASE_PROMPT
from palaver.app.dataclasses.run_deps import RunDeps


class AgentManager:
    # TODO: Rework this mess together with the Agent model.
    """Manages AI agents and their interactions with chat flow logic"""

    def __init__(self, agents: list[Agent] = None):
        self.agents: dict[str, Agent] = {}
        if agents is not None:
            self.agents = {
                agent.id: agent for agent in agents
            }

    def create_agent(
        self, agent_config: AgentConfig, provider_config: ProviderConfig
    ) -> Agent | None:
        """Create an agent from an AgentConfig"""
        agent = Agent(
            agent_info=AgentInfo.from_config(agent_config),
            provider_config=provider_config,
        )
        self.agents[agent.id] = agent
        return agent

    def get_agent(self, agent_id: str) -> Agent | None:
        """Get an agent by ID"""
        return self.agents.get(agent_id)
    
    def get_agent_info(self, agent_id: str) -> AgentInfo | None:
        """Get an agent by ID"""
        agent = self.agents.get(agent_id)
        if agent is None:
            return None
        return agent.info

    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent by ID"""
        agent = self.get_agent(agent_id)
        if not agent:
            return False

        # Remove from agents dict
        del self.agents[agent_id]
        return True

    def load_default_agents(self, llm_config: LLMConfig) -> list[Agent]:
        """Load default agents from config"""
        agents = []
        for agent_config in llm_config.agents:
            for provider_config in llm_config.providers:
                if provider_config.name == agent_config.provider:
                    break
                if provider_config == llm_config.providers[-1]:
                    raise ValueError(
                        f"Provider '{agent_config.provider}' nor found for agent '{agent_config.name}'"
                    )
            agent = self.create_agent(agent_config, provider_config)
            agents.append(agent)
        return agents
    
    def create_system_prompt(
        self,
        agent_id: str,
        other_agent_ids: list[str],
    ) -> str:
        agent = self.get_agent(agent_id)
        other_agents: list[Agent] = []
        for aid in other_agent_ids:
            if (agent := self.get_agent(aid)) is not None:
                other_agents.append(agent)

        other_agent_descriptions = "\n".join(
            [f"- AGENT ({agent.name}): {agent.description}" for agent in other_agents]
        )
        agent_prompt = self.get_agent(agent_id).system_prompt
        prompt = (
            BASE_PROMPT.replace("[[agent_name]]", agent.name)
            .replace("[[agent_description]]", agent.description)
            .replace("[[other_agent_descriptions]]", other_agent_descriptions)
            .replace("[[agent_prompt]]", agent_prompt)
        )
        return prompt

    def _construct_user_message(
        self, content: str, sender: str, role: Literal[RoleEnum.AGENT, RoleEnum.USER]
    ) -> ModelRequest:
        message = ChatroomMessage(sender=sender, role=role, content=content)
        return ModelRequest.user_text_prompt(message.model_dump_json())

    def _inject_system_prompt(
        self, prompt: str, messages: list[Message]
    ) -> list[ModelMessage]:
        first = messages[0]
        system_part = SystemPromptPart(content=prompt)
        if (
            isinstance(first, ModelRequest)
            and first.parts[0].part_kind != "system-prompt"
        ):
            first.parts = [system_part] + first.parts
        else:
            messages = [ModelRequest(parts=[system_part])] + messages

    def _construct_messages(
        self, agent_id: str, system_prompt: str, messages: list[Message]
    ) -> list[ModelMessage]:
        model_messages = []
        for msg in messages:
            if msg.role == RoleEnum.USER:
                model_messages.append(
                    self._construct_user_message(msg.content, "USER", RoleEnum.USER)
                )
            else:
                sender = msg.sender
                if sender != agent_id:
                    model_messages.append(
                        self._construct_user_message(
                            msg.content, sender, RoleEnum.AGENT
                        )
                    )
                else:
                    if not msg.content:
                        continue
                    model_messages.append(
                        ModelResponse(parts=[TextPart(content=msg.content)])
                    )
        self._inject_system_prompt(system_prompt, model_messages)
        return model_messages

    async def _generate_llm_response(
        self,
        agent: Agent,
        message: Message,
        chat_history: list[Message],
        system_prompt: str,
    ) -> tuple[ChatroomMessage | str, bool]:
        message_history = self._construct_messages(
            agent.id, system_prompt, chat_history + [message]
        )
        try:
            result = await agent._inner.run(
                user_prompt=message_history[-1].parts[0].content,
                message_history=message_history[:-1],
            )
            return result.output, True
        except Exception as e:
            error_msg = f"Error generating response: {str(e)}"
            logger.error(error_msg)
            return error_msg, False

    async def _generate_llm_response_streaming_text(
        self,
        agent: Agent,
        message: Message,
        chat_history: list[Message],
        system_prompt: str,
        run_deps: RunDeps,
        tools: list,
        delta: bool = None,
    ) -> AsyncGenerator[str, None]:
        delta = False if delta is None else delta
        message_history = self._construct_messages(
            agent.id, system_prompt, chat_history + [message]
        )

        async with agent._inner.run_stream(
            user_prompt=message_history[-1].parts[0].content,
            message_history=message_history[:-1],
            deps=run_deps,
            toolsets=[FunctionToolset(tools=tools)],
            output_type=str,
        ) as result:
            async for message in result.stream_text(delta=delta):
                yield message

    def _agent_run_stream(
        self,
        agent: Agent,
        message: Message,
        chat_history: list[Message],
        system_prompt: str,
        run_deps: RunDeps,
        tools: list,
        event_stream_handler=None,
    ):
        message_history = self._construct_messages(
            agent.id, system_prompt, chat_history + [message]
        )

        stream = agent._inner.run_stream(
            user_prompt=message_history[-1].parts[0].content,
            message_history=message_history[:-1],
            deps=run_deps,
            toolsets=[FunctionToolset(tools=tools)],
            event_stream_handler=event_stream_handler,
        )
        return stream

    def _agent_run(
        self,
        agent: Agent,
        message: Message,
        chat_history: list[Message],
        system_prompt: str,
        run_deps: RunDeps,
        **kwargs,
    ):
        message_history = self._construct_messages(
            agent.id, system_prompt, chat_history + [message]
        )

        run = agent.inner.run(
            user_prompt=message_history[-1].parts[0].content,
            message_history=message_history[:-1],
            deps=run_deps,
            **kwargs,
        )
        return run

    def _agent_run_stream_events(
        self,
        agent: Agent,
        message: Message,
        chat_history: list[Message],
        system_prompt: str,
        run_deps: RunDeps,
        **kwargs,
    ):
        message_history = self._construct_messages(
            agent.id, system_prompt, chat_history + [message]
        )

        stream = agent._inner.run_stream_events(
            user_prompt=message_history[-1].parts[0].content,
            message_history=message_history[:-1],
            deps=run_deps,
            **kwargs,
        )
        return stream

    def _parse_agent_response(
        self, agent_id: str, response_text: str, success: bool
    ) -> AgentResponse:
        response = AgentResponse(
            agent_id=agent_id,
            response=response_text,
            timestamp=datetime.now().isoformat(),
        )
        if not success:
            response.response = ""
            response.error = response_text
        return response

    async def generate_response(
        self,
        agent_id: str,
        message: Message | str,
        chat_history: list[Message],
        system_prompt: str,
        message_target: MessageTarget | None = None,
    ) -> AgentResponse:
        """Generate a response from an agent using chat flow logic"""

        # Step 1: Message targeting (if specified)
        target_agent_id = agent_id
        if message_target and message_target.is_targeted():
            # Message is targeted to specific agents
            if agent_id not in message_target.agent_ids:
                raise ValueError(f"Agent {agent_id} is not a target for this message")

        if isinstance(message, str):
            message = Message(sender="user", role=RoleEnum.USER, content=message)

        response_text, success = await self._generate_llm_response(
            self.get_agent(target_agent_id),
            message,
            chat_history,
            system_prompt=system_prompt,
        )
        return self._parse_agent_response(
            agent_id=target_agent_id,
            response=response_text,
            success=success,
        )

    def list_agents(self) -> list[AgentInfo]:
        """List all available agents"""
        return list(agent.info for agent in self.agents.values())


class AgentService:
    """Service for managing AI agents with chat flow logic"""

    def __init__(self):
        self.llm_config = LLMConfig()
        self.agent_manager = AgentManager()

        # Load default agents from config
        self.agent_manager.load_default_agents(self.llm_config)

    def _save_llm_config(self):
        LLMConfig.save_updates(self.llm_config.model_dump())

    def create_agent(self, config: AgentConfig) -> AgentInfo | None:
        """Create a new agent with custom configuration"""
        provider_config = self.get_provider(config.provider)
        new_agent = self.agent_manager.create_agent(config, provider_config)
        if new_agent is None:
            return

        self.llm_config.agents.append(config)
        self._save_llm_config()
        return new_agent.info

    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent by ID"""
        if not self.agent_manager.delete_agent(agent_id):
            return False

        # Remove from llm_config.agents list
        self.llm_config.agents = [
            agent_config
            for agent_config in self.llm_config.agents
            if agent_config.name != agent_id
        ]

        self._save_llm_config()
        return True

    def get_agent_config(self, agent_id: str) -> AgentConfig | None:
        """Get the configuration for an agent"""
        agent = self.get_agent(agent_id)
        for cfg in self.llm_config.agents:
            if cfg.name == agent.name:
                return cfg

        return None

    def update_agent_config(self, agent_id: str, config_update: dict[str, Any]) -> bool:
        """Update an agent's configuration"""
        agent_config = self.get_agent_config(agent_id)
        if not agent_config:
            return False

        # Update the agent's config
        for key, value in config_update.items():
            if hasattr(agent_config, key):
                setattr(agent_config, key, value)

        self._save_llm_config()

        # Update the agent itself
        agent = self.get_agent(agent_id)
        for key, value in config_update.items():
            if hasattr(agent, key):
                setattr(agent, key, value)

        return True

    def create_provider(self, config: ProviderConfig) -> ProviderConfig | None:
        """Add a new provider configuration"""
        # Check if provider already exists
        for provider in self.llm_config.providers:
            if provider.name == config.name:
                return None  # Provider already exists

        self.llm_config.providers.append(config)
        self._save_llm_config()
        return config

    def get_provider(self, provider_name: str) -> ProviderConfig | None:
        """Get a provider by name"""
        for provider in self.llm_config.providers:
            if provider.name == provider_name:
                return provider

    def update_provider_config(
        self, provider_name: str, config_update: dict[str, Any]
    ) -> bool:
        """Update a provider's configuration"""
        provider = self.get_provider(provider_name)
        if not provider:
            return False

        for key, value in config_update.items():
            if hasattr(provider, key):
                setattr(provider, key, value)

        self._save_llm_config()

        return True

    def delete_provider(self, provider_name: str) -> bool:
        """Delete a provider by name"""
        # Check if any agents are using this provider
        for agent_config in self.llm_config.agents:
            if agent_config.provider == provider_name:
                return False  # Cannot delete provider that's in use by agents

        # Remove provider from config
        original_length = len(self.llm_config.providers)
        self.llm_config.providers = [
            provider
            for provider in self.llm_config.providers
            if provider.name != provider_name
        ]

        if len(self.llm_config.providers) == original_length:
            return False  # Provider not found

        self._save_llm_config()
        return True

    async def list_models(self, provider_name: str) -> list[str]:
        provider_config = self.get_provider(provider_name)
        if provider_config is None:
            raise ValueError(f"Provider '{provider_name}' not found")

        return await ProviderModels.list_models(provider_config)

    def get_agent(self, agent_id: str) -> AgentInfo | None:
        """Get an agent by ID"""
        return self.agent_manager.get_agent_info(agent_id)

    def list_agents(self) -> list[AgentInfo]:
        """List all available agents"""
        return self.agent_manager.list_agents()


@lru_cache
def get_agent_service() -> AgentService:
    return AgentService()
