from palaver.app.init import init
init()

import asyncio
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from palaver.app.api import chatrooms, agents, providers, keys
from palaver.app.connection_manager import manager
from palaver.app.constants import UI_DIR
from palaver.app.dataclasses.events import ChatMessageEvent, UserLeftEvent
from palaver.app.dataclasses.message import Message
from palaver.app.services.chatroom_service import generate_agent_response_streaming


app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API routers
app.include_router(chatrooms.router)
app.include_router(agents.router)
app.include_router(providers.router)
app.include_router(keys.router)

@app.websocket("/ws/{chatroom_id}")
async def websocket_endpoint(websocket: WebSocket, chatroom_id: str):
    await manager.connect(websocket, chatroom_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message["type"] == "chat_message":
                print("Entered websocket")
                chat_event = ChatMessageEvent.model_validate(message)
                # Broadcast message to all participants in the chatroom
                await manager.broadcast(
                    chat_event.model_dump_json(),
                    chatroom_id
                )
                
                # If target agents specified, generate responses asynchronously
                target_agent_ids = chat_event.target_agent_ids
                if target_agent_ids:
                    user_message = Message(
                        sender=chat_event.sender,
                        role="user",
                        content=chat_event.content,
                        target_agent_ids=target_agent_ids
                    )
                    
                    for agent_id in target_agent_ids:
                        asyncio.create_task(
                            generate_agent_response_streaming(
                                chatroom_id=chatroom_id,
                                agent_id=agent_id,
                                user_message=user_message
                            )
                        )
            elif message["type"] == "agent_command":
                # Handle agent-specific commands
                await handle_agent_command(message, websocket, chatroom_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, chatroom_id)
        await manager.broadcast(
            UserLeftEvent(message="A user left the chatroom").model_dump_json(),
            chatroom_id,
        )

app.mount("/", StaticFiles(directory=UI_DIR / "dist", html=True), name="agent-chatroom")

async def handle_agent_command(message: dict, websocket: WebSocket, chatroom_id: str):
    """Handle commands related to AI agents"""
    command = message.get("command")
    
    if command == "create_agent":
        # This would now use the service layer
        await websocket.send_text(json.dumps({
            "type": "agent_command_response",
            "command": "create_agent",
            "message": "Agent creation should be done via REST API now"
        }))
    
    elif command == "add_agent_to_chatroom":
        # This would now use the service layer
        await websocket.send_text(json.dumps({
            "type": "agent_command_response",
            "command": "add_agent_to_chatroom", 
            "message": "Agent management should be done via REST API now"
        }))

def main():
    import os
    import uvicorn
    port = int(env_port) if (env_port := os.getenv("BACKEND_API_PORT")) is not None else 8000
    uvicorn.run(app, port=port)


if __name__ == "__main__":
    main()
