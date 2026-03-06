from fastapi import APIRouter, HTTPException

from palaver.app.config import AgentConfig
from palaver.app.dataclasses.agent import AgentInfo, AgentResponse, CreateAgentRequest, DeleteResponse
from palaver.app.dataclasses.message import Message, SendMessageRequest
from palaver.app.models.agent import Agent
from palaver.app.services.agent_service import get_agent_service


router = APIRouter(prefix="/api/agents", tags=["agents"])
agent_service = get_agent_service()


@router.get("/", response_model=list[AgentInfo])
async def list_agents():
    """List all agents"""
    return agent_service.list_agents()

@router.get("/{agent_id}", response_model=AgentInfo)
async def get_single_agent(agent_id: str):
    """Get a specific agent"""
    agent = agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@router.post("/{agent_id}/respond", response_model=AgentResponse)
async def generate_agent_response(agent_id: str, request: SendMessageRequest):
    """Generate a response from an agent"""
    message = request.message
    chat_history = request.history
    
    try:
        response = await agent_service.generate_agent_response(
            agent_id, message, chat_history
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

@router.post("/", response_model=AgentInfo)
async def create_agent(request: CreateAgentRequest):
    """Create a new agent"""
    agent = agent_service.create_agent(AgentConfig.model_validate(request.model_dump()))
    if agent is None:
        raise HTTPException(status_code=400, detail="Agent already exists")
    else:
        return agent

@router.put("/{agent_id}", response_model=AgentInfo)
async def update_agent(agent_id: str, request: CreateAgentRequest):
    """Update an existing agent"""
    # Name cannot be changed this way as it's the ID, so ensure it matches
    if agent_id != request.name:
        raise HTTPException(status_code=400, detail="Cannot change agent name (ID)")
        
    success = agent_service.update_agent_config(agent_id, request.model_dump())
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    return agent_service.get_agent(agent_id)

@router.post("/test", response_model=AgentResponse)
async def test_agent_connection(request: CreateAgentRequest):
    """Test an agent configuration without saving it"""
    
    config = AgentConfig.model_validate(request.model_dump())
    agent_info = AgentInfo.from_config(config)
    provider_config = agent_service.get_provider(config.provider)
    temp_agent = Agent(agent_info, provider_config)
    
    test_message = Message(
        sender="system", 
        role="user", 
        content="Please reply with 'Connection successful' to confirm you are online."
    )
    
    try:
        response_text, success = await agent_service.agent_manager._generate_llm_response(
            temp_agent, 
            test_message, 
            []
        )
        resp = agent_service.agent_manager._parse_agent_response(
            agent_id=temp_agent.id,
            response_text=response_text,
            success=success
        )
        return resp
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

@router.delete("/{agent_id}", response_model=DeleteResponse)
async def delete_agent(agent_id: str):
    """Delete an agent"""
    success = agent_service.delete_agent(agent_id)
    if success:
        return DeleteResponse(success=True, message="Agent deleted successfully")
    else:
        raise HTTPException(status_code=404, detail="Agent not found")