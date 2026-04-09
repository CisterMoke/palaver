import re
import uuid

from datetime import datetime
from loguru import logger

import palaver.app.database.db as db

from palaver.app.agent_loop.loop import AgentLoop
from palaver.app.config import AgentLoopConfig
from palaver.app.dataclasses.chatroom import Chatroom, ChatroomCreate, ChatroomUpdate
from palaver.app.dataclasses.message import ChatMessage, Message
from palaver.app.event_bridges.ui import UIEventBridge
from palaver.app.event_handlers.chatroom import ChatroomEventHandler
from palaver.app.services.agent_service import get_agent_service


def create_chatroom(create_request: ChatroomCreate) -> Chatroom:
    """Create a new chatroom"""
    params = {k: v for k, v in create_request.model_dump().items() if v is not None}
    chatroom = Chatroom.model_validate(params)
    db.save_chatroom(chatroom)
    return chatroom


def get_chatroom(chatroom_id: str) -> Chatroom | None:
    """Get a chatroom by ID"""
    try:
        return db.get_chatroom(chatroom_id)
    except ValueError:
        logger.warning(f"Could not find chatroom with id '{chatroom_id}'")


def update_chatroom(chatroom_id: str, update_request: ChatroomUpdate):
    """Get a chatroom by ID"""
    chatroom = get_chatroom(chatroom_id)
    if chatroom is None:
        return

    params = chatroom.model_dump() | {
        k: v for k, v in update_request.model_dump().items() if v is not None
    }
    new_chatroom = Chatroom.model_validate(params)
    db.save_chatroom(new_chatroom)
    return


def get_all_chatrooms() -> list[Chatroom]:
    """Get all chatrooms"""
    return db.load_chatrooms()


def add_agent_to_chatroom(chatroom_id: str, agent_id: str) -> bool:
    """Add an agent to a chatroom"""
    chatroom = get_chatroom(chatroom_id)
    if chatroom is None:
        return False

    chatroom.agents.append(agent_id)
    db.save_chatroom(chatroom)
    return True


def remove_agent_from_chatroom(chatroom_id: str, agent_id: str) -> bool:
    """Remove an agent from a chatroom"""
    chatroom = get_chatroom(chatroom_id)
    if chatroom is None:
        return False

    agents = chatroom.agents
    if agent_id in agents:
        chatroom.agents = [a for a in agents if a != agent_id]

    db.save_chatroom(chatroom)
    return True


def get_chatroom_agent_ids(chatroom_id: str) -> list[str]:
    """Get all agents in a chatroom"""
    chatroom = get_chatroom(chatroom_id)
    if chatroom is None:
        return []

    return chatroom.agents


def filter_target_ids(chatroom_id: str, target_ids: list[str]) -> list[str] | None:
    filtered = []
    chatroom_agent_ids = set(get_chatroom_agent_ids(chatroom_id))
    agent_service = get_agent_service()
    for target_id in target_ids:
        if (
            target_id not in chatroom_agent_ids
            or agent_service.get_agent(target_id) is None
        ):
            continue
        filtered.append(target_id)
    return None if not filtered else filtered


def store_chat_message(chatroom_id: str, chat_message: ChatMessage):
    db.save_message(chatroom_id, chat_message)


def create_message(chatroom_id: str, message: Message) -> ChatMessage:
    """Create a new message in a chatroom"""
    message_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()

    chat_message = ChatMessage(
        id=message_id,
        chatroom_id=chatroom_id,
        timestamp=timestamp,
        **message.model_dump(),
    )
    if chat_message.recipients:
        chat_message.recipients = filter_target_ids(
            chatroom_id, chat_message.recipients
        )
    store_chat_message(chatroom_id, chat_message)

    return chat_message


def get_chatroom_messages(
    chatroom_id: str, limit: int | None = None
) -> list[ChatMessage]:
    """Get messages from a chatroom"""
    if limit is None:
        return db.load_messages(chatroom_id)

    return db.load_messages(chatroom_id)[-limit:]


def extract_target_ids(chatroom_id, agent_id: str, text: str) -> list[str] | None:
    target_ids = []
    pattern = r"@(\w+)"
    for match in re.finditer(pattern, text):
        target_id = match.group(1)
        if target_id != agent_id:
            target_ids.append(match.group(1))
    return filter_target_ids(chatroom_id, target_ids)


async def run_agent_loop(
        chatroom_id: str,
        agent_id: str,
        user_message: Message,
        chat_history: list[ChatMessage],
    ):
    agent_ids = get_chatroom_agent_ids(chatroom_id)
    agent_service = get_agent_service()
    agents = [agent_service.agent_manager.get_agent(aid) for aid in agent_ids]

    chatroom = get_chatroom(chatroom_id)
    config = AgentLoopConfig(
        max_subagent_calls=chatroom.max_subagent_calls if chatroom.limit_subagent_calls else None,
        max_message_history=chatroom.max_message_history,
        agent_routing=chatroom.routing_type,
    )
    
    loop = AgentLoop(
        agents=agents,
        config=config
    )
    loop.add_event_bridge(UIEventBridge)
    loop.add_event_handler(ChatroomEventHandler(chatroom_id))

    await loop.run(
        agent_id=agent_id,
        user_message=user_message,
        chat_history=chat_history,
    )