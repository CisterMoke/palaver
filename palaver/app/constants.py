import os

from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1] if (custom_root := os.getenv("PALAVER_ROOT")) is None else Path(custom_root)
CONFIG_DIR = Path.home() / ".palaver" if (custom_home := os.getenv("PALAVER_HOME")) is None else Path(custom_home)

CONFIG_FILE = CONFIG_DIR / "config.toml"
ENV_FILE = CONFIG_DIR / ".env"

DATA_DIR = CONFIG_DIR / "data"
CHATROOMS_DIR = DATA_DIR / "chatrooms"
UI_DIR = PROJECT_ROOT / "ui"

DEFAULT_AGENT_NAME = "AI Assistant"
DEFAULT_AGENT_PROMPT = "You are a helpful AI assistant."

SUPPORTED_SERVICES = [
  "alibaba",
  "anthropic",
  "azure",
  "bedrock",
  "cerebras",
  "cohere",
  "deepseek",
  "fireworks",
  "github",
  "google",
  "grok",
  "groq",
  "heroku",
  "huggingface",
  "litellm",
  "mistral",
  "moonshotai",
  "nebius",
  "ollama",
  "openai",
  "openrouter",
  "ovhcloud",
  "sambanova",
  "sentence_transformers",
  "together",
  "vercel",
  "xai",
]

MAX_DEPTH_MESSAGE = "Agent unavailable, please direct your message directly to the user."