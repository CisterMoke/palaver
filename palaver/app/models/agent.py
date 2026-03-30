import os
import typing

from loguru import logger
from pydantic_ai import Agent as PydanticAgent
from pydantic_ai.agent import ModelSettings
from pydantic_ai.models import infer_model, KnownModelName
from pydantic_ai.providers import Provider, infer_provider_class

from palaver.app.config import ProviderConfig
from palaver.app.dataclasses.agent import AgentInfo
from palaver.app.dataclasses.run_deps import RunDeps


class Agent:
    @classmethod
    def _provider_factory(cls, provider_config: ProviderConfig):
        def get_provider(*args, **kwargs) -> Provider:
            provider_class = infer_provider_class(provider_config.service)
            api_base = None if not provider_config.api_base else provider_config.api_base
            if not provider_config.api_key_env_var:
                return provider_class(base_url=api_base)
            
            if (api_key := os.getenv(provider_config.api_key_env_var)) is None:
                raise ValueError(f"Cannot initialize provider '{provider_config.name}': '{provider_config.api_key_env_var}' not defined")
            return provider_class(api_key=api_key, base_url=api_base)
        return get_provider

    def __init__(self, agent_info: AgentInfo, provider_config: ProviderConfig):
        self.info = agent_info
        self._inner = self._init_inner_agent(provider_config)

    def _init_inner_agent(self, provider_config: ProviderConfig) -> PydanticAgent:
        full_name = f"{provider_config.service}:{self.model}"
        agent_model = infer_model(model=full_name, provider_factory=self._provider_factory(provider_config))
        model_settings = ModelSettings(
            temperature=None if self.info.temperature < 0 else self.info.temperature
        )
        pydantic_agent = PydanticAgent(
            model=agent_model,
            instructions=None if not self.instructions else self.instructions,
            model_settings=model_settings,
            deps_type=RunDeps,
            end_strategy="exhaustive",
        )
        return pydantic_agent

    @property
    def id(self) -> str:
        return self.info.id

    @property
    def instructions(self) -> list[str]:
        return self.info.instructions
    
    @property
    def model(self) -> str:
        return self.info.model
    
    @property
    def name(self) -> str:
        return self.info.name
    
    @property
    def system_prompt(self) -> str:
        return self.info.prompt


def _get_known_models_mapping() -> dict[str, list[str]]:
    known_models = typing.get_args(KnownModelName.__value__)
    model_map = dict()
    for model in known_models:
        try:
            provider_name, model_name = model.split(":", 1)
        except ValueError:
            continue
        model_map[provider_name] = model_map.get(provider_name, []) + [model_name]
    return model_map


class ProviderModels:
    known_models = _get_known_models_mapping()

    @classmethod
    async def list_models(cls, provider_config: ProviderConfig) -> list[str]:
        provider = Agent._provider_factory(provider_config)()
        client = provider.client
        try:
            # TODO add support for more providers
            if provider.name == "mistral":
                response = await client.models.list_async()
                return [model_data.id for model_data in response.data]
            else:
                response = await client.models.list()
                return [model_data.id for model_data in response.data]
        except Exception as e:
            logger.error(f"Error trying to list models for '{provider_config.name}'{e}")
            return cls.known_models.get(provider_config.service, [])
        
