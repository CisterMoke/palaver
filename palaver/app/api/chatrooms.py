from fastapi import APIRouter, HTTPException, BackgroundTasks

import palaver.app.services.chatroom_service as chat_service

from palaver.app.dataclasses.agent import AddAgentRequest
from palaver.app.dataclasses.chatroom import Chatroom, ChatroomCreate, ChatroomUpdate
from palaver.app.dataclasses.events import ChatMessageEvent
from palaver.app.dataclasses.message import ChatMessage, Message
from palaver.app.connection_manager import manager


router = APIRouter(prefix="/api/chatrooms", tags=["chatrooms"])


@router.post("/", response_model=Chatroom)
async def create_new_chatroom(request: ChatroomCreate):
    """Create a new chatroom"""
    return chat_service.create_chatroom(request)


@router.get("/", response_model=list[Chatroom])
async def list_chatrooms():
    """List all chatrooms"""
    return chat_service.get_all_chatrooms()


@router.get("/{chatroom_id}", response_model=Chatroom)
async def get_single_chatroom(chatroom_id: str):
    """Get a specific chatroom"""
    chatroom = chat_service.get_chatroom(chatroom_id)
    if not chatroom:
        raise HTTPException(status_code=404, detail="Chatroom not found")
    return chatroom


@router.post("/{chatroom_id}", response_model=Chatroom)
async def update_chatroom_settings(chatroom_id: str, request: ChatroomUpdate):
    """Update a specific chatroom"""
    chat_service.update_chatroom(chatroom_id, request)


@router.get("/{chatroom_id}/agents", response_model=list[str])
async def list_chatroom_agents(chatroom_id: str):
    """List agents in a chatroom"""
    return chat_service.get_chatroom_agents(chatroom_id)


@router.post("/{chatroom_id}/agents", response_model=dict)
async def add_agent_to_chatroom_endpoint(chatroom_id: str, add_agent_request: AddAgentRequest):
    """Add an agent to a chatroom"""
    agent_id = add_agent_request.agent_id
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id is required")
    
    success = chat_service.add_agent_to_chatroom(chatroom_id, agent_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add agent to chatroom")
    
    return {"success": True, "agent_id": agent_id, "chatroom_id": chatroom_id}


@router.delete("/{chatroom_id}/agents/{agent_id}", response_model=dict)
async def remove_agent_from_chatroom_endpoint(chatroom_id: str, agent_id: str):
    """Remove an agent from a chatroom"""
    success = chat_service.remove_agent_from_chatroom(chatroom_id, agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Chatroom not found")
    return {"success": True, "agent_id": agent_id, "chatroom_id": chatroom_id}


@router.get("/{chatroom_id}/messages", response_model=list[ChatMessage])
async def list_chatroom_messages(chatroom_id: str, limit: int = None):
    """Get messages from a chatroom"""
    return chat_service.get_chatroom_messages(chatroom_id, limit)


@router.post("/{chatroom_id}/messages", response_model=ChatMessage)
async def send_message(chatroom_id: str, message: Message, background_tasks: BackgroundTasks):
    """Send a message to a chatroom. If it targets agents, stream their responses in the background."""
    chatroom = chat_service.get_chatroom(chatroom_id)
    chat_history = chat_service.get_chatroom_messages(chatroom_id, limit=chatroom.max_message_history)
    stored_message = chat_service.create_message(
        chatroom_id=chatroom_id,
        message=message
    )
    
    await manager.broadcast(
        ChatMessageEvent.model_validate(stored_message.model_dump()).model_dump_json(),
        chatroom_id
    )
    
    for agent_id in stored_message.target_agent_ids or []:
        background_tasks.add_task(
            chat_service.generate_agent_response_streaming,
            chatroom_id=chatroom_id,
            agent_id=agent_id,
            user_message=message,
            chat_history=chat_history,
        )
            
    return stored_message