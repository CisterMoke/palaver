import os
import re
import uuid

from datetime import datetime
from pydantic_core import to_jsonable_python

from palaver.app.database.db import (
    _get_chatroom_path, _read_json_file, _write_json_file,
    CHATROOMS_DIR,
)

from palaver.app.connection_manager import manager
from palaver.app.dataclasses.chatroom import Chatroom
from palaver.app.dataclasses.events import AgentResponseStartEvent, AgentResponseChunkEvent, AgentResponseCompleteEvent, AgentResponseErrorEvent
from palaver.app.dataclasses.message import ChatMessage, Message
from palaver.app.services.agent_service import get_agent_service
from palaver.app.tools import send_agent_tool, Metadata


agent_service = get_agent_service()


def create_chatroom(name: str, description: str = "") -> Chatroom:
    """Create a new chatroom"""
    chatroom_id = str(uuid.uuid4())
    chatroom_data = {
        "id": chatroom_id,
        "name": name,
        "description": description,
        "agents": [],
        "messages": [],
        "created_at": datetime.now().isoformat()
    }
    
    file_path = _get_chatroom_path(chatroom_id)
    _write_json_file(file_path, chatroom_data)
    
    return Chatroom(id=chatroom_id, name=name, description=description)


def get_chatroom(chatroom_id: str) -> Chatroom | None:
    """Get a chatroom by ID"""
    file_path = _get_chatroom_path(chatroom_id)
    chatroom_data = _read_json_file(file_path)
    
    if chatroom_data:
        return Chatroom(
            id=chatroom_data["id"], 
            name=chatroom_data["name"], 
            description=chatroom_data.get("description", "")
        )
    return None


def get_all_chatrooms() -> list[Chatroom]:
    """Get all chatrooms"""
    chatrooms = []
    if os.path.exists(CHATROOMS_DIR):
        for filename in os.listdir(CHATROOMS_DIR):
            if filename.endswith(".json"):
                file_path = os.path.join(CHATROOMS_DIR, filename)
                chatroom_data = _read_json_file(file_path)
                if chatroom_data:
                    chatrooms.append(Chatroom(
                        id=chatroom_data["id"],
                        name=chatroom_data["name"],
                        description=chatroom_data.get("description", "")
                    ))
    return chatrooms


def add_agent_to_chatroom(chatroom_id: str, agent_id: str) -> bool:
    """Add an agent to a chatroom"""
    chatroom_file = _get_chatroom_path(chatroom_id)
    chatroom_data = _read_json_file(chatroom_file)
    
    if not chatroom_data:
        return False
    
    if agent_id not in chatroom_data.get("agents", []):
        chatroom_data["agents"].append(agent_id)
        _write_json_file(chatroom_file, chatroom_data)
    
    return True


def remove_agent_from_chatroom(chatroom_id: str, agent_id: str) -> bool:
    """Remove an agent from a chatroom"""
    chatroom_file = _get_chatroom_path(chatroom_id)
    chatroom_data = _read_json_file(chatroom_file)

    if not chatroom_data:
        return False

    agents = chatroom_data.get("agents", [])
    if agent_id in agents:
        chatroom_data["agents"] = [a for a in agents if a != agent_id]
        _write_json_file(chatroom_file, chatroom_data)

    return True


def get_chatroom_agents(chatroom_id: str) -> list[str]:
    """Get all agents in a chatroom"""
    chatroom_file = _get_chatroom_path(chatroom_id)
    chatroom_data = _read_json_file(chatroom_file)
    
    if chatroom_data and "agents" in chatroom_data:
        return chatroom_data["agents"]

   
def filter_target_ids(chatroom_id: str, target_ids: list[str]) -> list[str] | None:
    filtered = []
    chatroom_agent_ids = set(get_chatroom_agents(chatroom_id))
    for target_id in target_ids:
        if target_id not in chatroom_agent_ids or agent_service.get_agent(target_id) is None:
            continue
        filtered.append(target_id)
    return None if not filtered else filtered


def store_chat_message(chatroom_id: str, chat_message: ChatMessage):
    chatroom_file = _get_chatroom_path(chatroom_id)
    chatroom_data = _read_json_file(chatroom_file)
    
    if chatroom_data:
        chatroom_data["messages"].append(to_jsonable_python(chat_message))
        _write_json_file(chatroom_file, chatroom_data)


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


def get_chatroom_messages(chatroom_id: str, limit: int = 100) -> list[ChatMessage]:
    """Get messages from a chatroom"""
    chatroom_file = _get_chatroom_path(chatroom_id)
    chatroom_data = _read_json_file(chatroom_file)
    
    messages = []
    if chatroom_data and "messages" in chatroom_data:
        # Get last 'limit' messages
        all_messages = chatroom_data["messages"][-limit:]
        for msg_data in all_messages:
            messages.append(ChatMessage.model_validate(msg_data))
    
    return messages


def extract_target_ids(chatroom_id, agent_id: str, text: str) -> list[str] | None:
    target_ids = []
    pattern = r"@(\w+)"
    for match in re.finditer(pattern, text):
        target_id = match.group(1)
        if target_id != agent_id:
            target_ids.append(match.group(1))
    return filter_target_ids(chatroom_id, target_ids)


async def generate_agent_response_streaming_old(chatroom_id: str, agent_id: str, user_message: Message, chat_history: list[ChatMessage]):
    """
    Generate a response from an agent, stream tokens via WebSocket, and persist the final message.
    """
    message_id = str(uuid.uuid4())
    other_agent_ids = [aid for aid in get_chatroom_agents(chatroom_id) if aid != agent_id]
    system_prompt = agent_service.create_system_prompt(agent_id, other_agent_ids)
    
    # Notify start
    await manager.broadcast(
        AgentResponseStartEvent(
            agent_id=agent_id,
            message_id=message_id,
        ).model_dump_json(),
        chatroom_id
    )
    
    full_response = ""
    try:
        async for delta in agent_service.generate_agent_response_streaming(
            agent_id=agent_id, 
            message=user_message, 
            chat_history=chat_history,
            system_prompt=system_prompt,
            delta=True
        ):
            full_response += delta
            await manager.broadcast(
                AgentResponseChunkEvent(
                    agent_id=agent_id,
                    message_id=message_id,
                    delta=delta,
                ).model_dump_json(),
                chatroom_id
            )
            
        # Complete! Persist it.
        timestamp = datetime.now().isoformat()
        target_ids = extract_target_ids(chatroom_id, agent_id, full_response)
        final_message = ChatMessage(
            id=message_id,
            chatroom_id=chatroom_id,
            sender=agent_id,
            role="assistant",
            content=full_response,
            timestamp=timestamp,
            target_agent_ids=target_ids,
        )
        store_chat_message(chatroom_id, final_message)
        await manager.broadcast(
            AgentResponseCompleteEvent(
                agent_id=agent_id,
                message_id=message_id,
                content=full_response
            ).model_dump_json(),
            chatroom_id
        )
        if target_ids is not None:
            chat_history.append(final_message)
            for agent_id in target_ids:
                await generate_agent_response_streaming(chatroom_id, agent_id, final_message, chat_history)
        
    except Exception as e:
        await manager.broadcast(
            AgentResponseErrorEvent(
                agent_id=agent_id,
                error=str(e),
            ).model_dump_json(),
            chatroom_id
        )

async def generate_agent_response_streaming(chatroom_id: str, agent_id: str, user_message: Message, chat_history: list[ChatMessage]) -> str:
    """
    Generate a response from an agent, stream tokens via WebSocket, and persist the final message.
    """
    other_agent_ids = [aid for aid in get_chatroom_agents(chatroom_id) if aid != agent_id]
    system_prompt = agent_service.create_system_prompt(agent_id, other_agent_ids)
    metadata = Metadata(
        chatroom_id=chatroom_id,
        agent_id=agent_id,
        chat_history=chat_history,
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
                role="assistant",
                content=curr_response,
                timestamp=timestamp,
                target_agent_ids=None,
            )
            store_chat_message(chatroom_id, reply_message)
    return curr_response