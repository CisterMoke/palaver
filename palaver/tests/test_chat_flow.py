from palaver.app.services.agent_service import get_agent_service
from palaver.app.dataclasses.message import Message
from palaver.app.dataclasses.agent import MessageTarget


agent_service = get_agent_service()


async def test_basic_response_generation():
    """Test basic response generation from an agent"""
    # Create a test agent
    agent = agent_service.create_agent(
        name="TestAgent",
        provider="mistral-belfius-gtu",
        model="devstral-medium-latest",
        prompt="You are a helpful test assistant."
    )
    
    # Test basic response
    response = await agent_service.generate_agent_response(
        agent_id=agent.id,
        message="Hello, how are you?",
        chat_history=[],
    )
    
    assert response.agent_id == agent.id
    assert response.response is not None
    assert len(response.response) > 0


async def test_message_targeting():
    """Test message targeting functionality"""
    # Create two agents
    agent1 = agent_service.create_agent(
        name="GeneralAgent",
        provider="mistral-belfius-gtu",
        model="devstral-medium-latest",
        prompt="You are a general purpose assistant."
    )
    
    _ = agent_service.create_agent(
        name="SpecialistAgent",
        provider="mistral-belfius-gtu", 
        model="devstral-medium-latest",
        prompt="You are a specialist in complex topics."
    )
    
    # Test targeted message
    message_target = MessageTarget(agent_ids=[agent1.id])
    targeted_response = await agent_service.generate_agent_response(
        agent_id=agent1.id,
        message="This is a targeted message",
        chat_history=[],
        message_target=message_target
    )
    
    assert targeted_response.agent_id == agent1.id
    assert targeted_response.response is not None


async def test_delegation():
    """Test message delegation between agents"""
    # Create two agents
    agent1 = agent_service.create_agent(
        name="GeneralAgent",
        provider="mistral-belfius-gtu",
        model="devstral-medium-latest",
        prompt="You are a general purpose assistant."
    )
    
    agent2 = agent_service.create_agent(
        name="SpecialistAgent",
        provider="mistral-belfius-gtu", 
        model="devstral-medium-latest",
        prompt="You are a specialist in complex topics."
    )
    
    # Test delegation
    delegation_response = await agent_service.delegate_message(
        agent_id=agent1.id,
        target_agent_ids=[agent2.id],
        message=Message(sender=agent1.id, role="assistant", content=f"I'm delegating this to {agent2.name}"),
        chat_history=[Message(sender="test_user", role="user", content=f"Hey {agent1.name}, can you solve this hard and complex task?")],
        is_dependent=True
    )
    
    assert delegation_response.agent_id == agent2.id
    assert delegation_response.response is not None
    assert len(delegation_response.response) > 0


async def test_chat_flow_integration():
    """Test the complete chat flow integration"""
    # Create agents
    general_agent = agent_service.create_agent(
        name="GeneralAgent",
        provider="mistral-belfius-gtu",
        model="devstral-medium-latest",
        prompt="You are a general purpose assistant.",
    )
    
    specialist_agent = agent_service.create_agent(
        name="SpecialistAgent",
        provider="mistral-belfius-gtu",
        model="devstral-medium-latest",
        prompt="You are a specialist in complex topics.",
    )
    
    # Test 1: Simple message that general agent can handle
    response1 = await agent_service.generate_agent_response(
        agent_id=general_agent.id,
        message="What time is it?",
        chat_history=[],
    )
    assert response1.agent_id == general_agent.id
    
    # Test 2: Complex message that should trigger delegation
    response2 = await agent_service.generate_agent_response(
        agent_id=general_agent.id,
        message="Explain quantum computing in detail",
        chat_history=[],
    )
    # This should either be handled by general agent or delegated to specialist
    assert response2.agent_id in [general_agent.id, specialist_agent.id]
    assert response2.response is not None