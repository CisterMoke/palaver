from fastapi import APIRouter, HTTPException

import palaver.app.services.chatroom_service as chat_service

from palaver.app.dataclasses.agent import AddAgentRequest, SetAgentsRequest
from palaver.app.dataclasses.chatroom import Chatroom, ChatroomCreate, ChatroomUpdate
from palaver.app.dataclasses.message import ChatMessage


router = APIRouter(prefix="/api/chatrooms", tags=["chatrooms"])


@router.post("/", response_model=Chatroom)
async def create_new_chatroom(request: ChatroomCreate):
    """Create a new chatroom"""
    return chat_service.create_chatroom(request)


@router.get("/", response_model=list[Chatroom])
async def list_chatrooms():
    """List all chatrooms"""
    return chat_service.get_all_chatrooms(_sorted=True)


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
    return chat_service.update_chatroom(chatroom_id, request)


@router.delete("/{chatroom_id}")
async def delete_chatroom(chatroom_id: str):
    """Delete a specific chatroom"""
    success = chat_service.delete_chatroom(chatroom_id)
    if not success:
        raise HTTPException(status_code=404, detail="Chatroom not found")
    return {"success": True, "chatroom_id": chatroom_id}


@router.get("/{chatroom_id}/agents", response_model=list[str])
async def list_chatroom_agents(chatroom_id: str):
    """List agents in a chatroom"""
    return chat_service.get_chatroom_agent_ids(chatroom_id)


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


@router.put("/{chatroom_id}/agents", response_model=dict)
async def set_chatroom_agents(chatroom_id: str, set_agents_request: SetAgentsRequest):
    """Set the chatroom agents"""
    agent_ids = set_agents_request.agent_ids
    
    success = chat_service.set_chatroom_agents(chatroom_id, agent_ids)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add agent to chatroom")
    
    return {"success": True, "agent_ids": agent_ids, "chatroom_id": chatroom_id}


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
