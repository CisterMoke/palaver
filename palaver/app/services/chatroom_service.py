import re
import uuid

from datetime import datetime
from loguru import logger

import palaver.app.database.db as db

from palaver.app.connection_manager import manager
from palaver.app.dataclasses.chatroom import Chatroom, ChatroomCreate, ChatroomUpdate
from palaver.app.dataclasses.events import AgentResponseStartEvent, AgentResponseChunkEvent, AgentResponseCompleteEvent
from palaver.app.dataclasses.message import ChatMessage, Message
from palaver.app.enums import RoleEnum
from palaver.app.services.agent_service import get_agent_service
from palaver.app.tools import send_agent_tool, Metadata


agent_service = get_agent_service()


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
    
    params = chatroom.model_dump() | {k: v for k, v in update_request.model_dump().items() if v is not None}
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


def get_chatroom_agents(chatroom_id: str) -> list[str]:
    """Get all agents in a chatroom"""
    chatroom = get_chatroom(chatroom_id)
    if chatroom is None:
        return []
    
    return chatroom.agents

   
def filter_target_ids(chatroom_id: str, target_ids: list[str]) -> list[str] | None:
    filtered = []
    chatroom_agent_ids = set(get_chatroom_agents(chatroom_id))
    for target_id in target_ids:
        if target_id not in chatroom_agent_ids or agent_service.get_agent(target_id) is None:
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
    if chat_message.target_agent_ids:
        chat_message.target_agent_ids = filter_target_ids(chatroom_id, chat_message.target_agent_ids)
    store_chat_message(chatroom_id, chat_message)
    
    return chat_message


def get_chatroom_messages(chatroom_id: str, limit: int = None) -> list[ChatMessage]:
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


def is_depth_exceeded(chatroom_id: str, depth: int) -> bool:
    chatroom = get_chatroom(chatroom_id)
    if chatroom is None:
        return True
    return chatroom.limit_agent_chains and depth > chatroom.max_chain_depth


async def generate_agent_response_streaming(chatroom_id: str, agent_id: str, user_message: Message, chat_history: list[ChatMessage], depth: int = 1) -> str:
    """
    Generate a response from an agent, stream tokens via WebSocket, and persist the final message.
    """
    other_agent_ids = [aid for aid in get_chatroom_agents(chatroom_id) if aid != agent_id]
    system_prompt = agent_service.create_system_prompt(agent_id, other_agent_ids)
    metadata = Metadata(
        chatroom_id=chatroom_id,
        agent_id=agent_id,
        chat_history=chat_history,
        chain_depth=depth,
        exceeds_max_depth=is_depth_exceeded(chatroom_id, depth)
    )
    
    async for event in agent_service.stream_agent_events(
        agent_id=agent_id, 
        message=user_message, 
        chat_history=chat_history,
        system_prompt=system_prompt,
        metadata=metadata,
        tools=[
            send_agent_tool(
                messaging_func=generate_agent_response_streaming,
                recipient_verifier=lambda aid: aid in get_chatroom_agents(chatroom_id))
            ]
    ):
        await manager.broadcast(event.model_dump_json(), chatroom_id)
        if isinstance(event, AgentResponseStartEvent):
            curr_response = ""
        elif isinstance(event, AgentResponseChunkEvent):
            curr_response += event.delta
        elif isinstance(event, AgentResponseCompleteEvent):
            timestamp = datetime.now().isoformat()
            reply_message = ChatMessage(
                id=event.message_id,
                chatroom_id=chatroom_id,
                sender=event.agent_id,
                role=RoleEnum.ASSISTANT,
                content=curr_response,
                timestamp=timestamp,
                target_agent_ids=None,
            )
            store_chat_message(chatroom_id, reply_message)
    return curr_response