from __future__ import annotations

import tomllib

from typing import Any, Literal

import tomli_w

from pydantic import BaseModel, Field, model_validator
from pydantic.fields import FieldInfo
from pydantic_core import to_jsonable_python
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
)

from palaver.app.constants import CONFIG_FILE


class ProviderConfig(BaseModel):
    name: str
    service: Literal["anthropic", "bedrock", "cohere", "google", "groq", "huggingface", "mistral", "openai"]
    api_base: str = ""
    api_key_env_var: str = ""


class AgentConfig(BaseModel):
    name: str
    provider: str
    model: str
    description: str
    prompt: str = "You are a helpful assistant."
    instructions: list[str] = []
    temperature: float = -1.0

    @model_validator(mode="before")
    @classmethod
    def set_description(cls, data):
        if not data.get("description"):
            if "model" not in data:
                raise ValueError("'model' not provided")
            data["description"] = f"AI Agent using {data['model']} model"
        return data


DEFAULT_PROVIDERS = [
    ProviderConfig(
        name="openai",
        service="openai",
        api_key_env_var="OPENAI_API_KEY",
    ),
    ProviderConfig(
        name="llamacpp",
        service="openai",
        api_base="http://127.0.0.1:8080/v1",
        api_key_env_var="",  # NOTE: if you wish to use --api-key in llama-server, change this value
    ),
]


DEFAULT_AGENTS = [
    AgentConfig(
        name="Chatty",
        provider="openai",
        model="gpt-5-mini",
        prompt="You are Chatty, a helpful AI assistant.",
    ),
    AgentConfig(
        name="Llama",
        provider="openai",
        model="llama",
        prompt="You are Llama, a helpful AI assistant.",
        description="AI Agent using a local llama.cpp model."
    ),
]


class TomlFileSettingsSource(PydanticBaseSettingsSource):
    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)
        self.toml_data = self._load_toml()

    def _load_toml(self) -> dict[str, Any]:
        file = CONFIG_FILE
        try:
            with file.open("rb") as f:
                return tomllib.load(f)
        except FileNotFoundError:
            return {}
        except tomllib.TOMLDecodeError as e:
            raise RuntimeError(f"Invalid TOML in {file}: {e}") from e
        except OSError as e:
            raise RuntimeError(f"Cannot read {file}: {e}") from e

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        return self.toml_data.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        return self.toml_data


class LLMConfig(BaseSettings):

    providers: list[ProviderConfig] = Field(
        default_factory=lambda: list(DEFAULT_PROVIDERS)
    )
    agents: list[AgentConfig] = Field(default_factory=lambda: list(DEFAULT_AGENTS))

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Define the priority of settings sources.

        Note: dotenv_settings and file_secret_settings are intentionally excluded. API keys and other
        non-config environment variables are stored in .env but loaded manually
        into os.environ for use by providers. Only TOML config are used for Pydantic settings.
        """
        return (
            init_settings,
            env_settings,
            TomlFileSettingsSource(settings_cls),
        )

    @classmethod
    def save_updates(cls, updates: dict[str, Any]) -> None:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        current_config = TomlFileSettingsSource(cls).toml_data

        def deep_merge(target: dict, source: dict) -> None:
            for key, value in source.items():
                if (
                    key in target
                    and isinstance(target.get(key), dict)
                    and isinstance(value, dict)
                ):
                    deep_merge(target[key], value)
                elif (
                    key in target
                    and isinstance(target.get(key), list)
                    and isinstance(value, list)
                ):
                    if key in {"providers", "agents"}:
                        target[key] = value
                    else:
                        target[key] = list(set(value + target[key]))
                else:
                    target[key] = value

        deep_merge(current_config, updates)
        cls.dump_config(
            to_jsonable_python(current_config, exclude_none=True, fallback=str)
        )

    @classmethod
    def dump_config(cls, config: dict[str, Any]) -> None:
        with open(CONFIG_FILE, "wb") as f:
            tomli_w.dump(config, f)
