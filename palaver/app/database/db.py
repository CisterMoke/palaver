import os

from pathlib import Path

from palaver.app.constants import CHATROOMS_DIR
from palaver.app.dataclasses.chatroom import Chatroom
from palaver.app.dataclasses.message import ChatMessage
from palaver.app.enums import RoleEnum


def init_db():
    """Initialize file storage directories"""
    os.makedirs(CHATROOMS_DIR, exist_ok=True)


def _ensure_dir(chatroom_id: str) -> Path:
    chatroom_dir = CHATROOMS_DIR / chatroom_id
    os.makedirs(chatroom_dir, exist_ok=True)
    return chatroom_dir


def save_chatroom(chatroom: Chatroom):
    chatroom_dir = _ensure_dir(chatroom.chatroom_id)
    with open(chatroom_dir / "config.json", "w") as f:
        f.write(chatroom.model_dump_json(by_alias=True))


def get_chatroom(chatroom_id: str) -> Chatroom:
    config_file = CHATROOMS_DIR / chatroom_id / "config.json"
    if not config_file.exists():
        print(config_file)
        raise ValueError(f"No chatroom found with id '{chatroom_id}'.")
    
    with open(config_file, "rb") as f:
        content = f.read()
        chatroom = Chatroom.model_validate_json(content, by_alias=True)
    assert chatroom.chatroom_id == chatroom_id
    return chatroom


def load_chatrooms() -> list[Chatroom]:
    chatrooms = []
    for file in CHATROOMS_DIR.rglob("config.json"):
        with open(file, "rb") as f:
            chatrooms.append(Chatroom.model_validate_json(f.read()))
    return chatrooms


def load_messages(chatroom_id: str) -> list[ChatMessage]:
    chat_messages = []
    messages_file = CHATROOMS_DIR / chatroom_id / "messages.jsonl"
    if not messages_file.exists():
        return chat_messages
    
    with open(messages_file, "rb") as f:
        for line in f:
            chat_message = ChatMessage.model_validate_json(line.rstrip(b"\n"))
            chat_messages.append(chat_message)
    return chat_messages


def save_message(chatroom_id: str, chat_message: ChatMessage):
    if chat_message.role == RoleEnum.ASSISTANT and not chat_message.content:
        raise ValueError("Content cannot be empty for assistant message.")

    message_json = chat_message.model_dump_json()
    messages_file = _ensure_dir(chatroom_id) / "messages.jsonl"
    
    if not messages_file.exists():
        with open(messages_file, "w") as f:
            f.write(f"{message_json}\n")
        return
    
    with open(messages_file, "a") as f:
        f.write(f"{message_json}\n")
    return
