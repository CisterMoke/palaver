import json
import os
from typing import Any

from palaver.app.constants import CHATROOMS_DIR

def init_db():
    """Initialize file storage directories"""
    os.makedirs(CHATROOMS_DIR, exist_ok=True)

def _get_chatroom_path(chatroom_id: str) -> str:
    """Get path to chatroom file"""
    return f"{CHATROOMS_DIR}/{chatroom_id}.json"

def _read_json_file(file_path: str) -> dict[str, Any]:
    """Read JSON file safely"""
    try:
        with open(file_path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _write_json_file(file_path: str, data: dict[str, Any]):
    """Write JSON file safely"""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)