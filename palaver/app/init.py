import dotenv
import os

from palaver.app.config import LLMConfig
from palaver.app.constants import CONFIG_FILE, ENV_FILE
from palaver.app.database.db import init_db


def init_env():
    default_env = {
        "OPENAI_API_KEY": "XXXXX"
    }

    if not os.path.isfile(ENV_FILE):
        os.makedirs(ENV_FILE.parent, exist_ok=True)
        with open(ENV_FILE, "w") as f:
            content = "\n".join([f"{k}='{v}'" for k, v in default_env.items()])
            f.write(content)
    
    dotenv.load_dotenv(ENV_FILE)


def init_config():
    default_config = LLMConfig()
    
    if not CONFIG_FILE.exists():
        os.makedirs(CONFIG_FILE.parent, exist_ok=True)
        LLMConfig.save_updates(default_config.model_dump())



def init():
    init_env()
    init_config()
    init_db()