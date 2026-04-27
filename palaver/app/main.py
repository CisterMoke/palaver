from palaver.app.init import init
init()

import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from palaver.app.api import chatrooms, agents, providers, keys
from palaver.app.websockets.handler import WebSocketHandler
from palaver.app.websockets.manager import get_ws_manager
from palaver.app.constants import UI_DIR


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
    ws_manager = get_ws_manager()
    ws_handler = WebSocketHandler(ws_manager, chatroom_id)
    await ws_manager.connect(websocket, chatroom_id)
    try:
        while True:
            data = await websocket.receive_json()
            await ws_handler.handle_data(data)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, chatroom_id)

app.mount("/", StaticFiles(directory=UI_DIR / "dist", html=True), name="agent-chatroom")

def main():
    import os
    import uvicorn
    port = int(env_port) if (env_port := os.getenv("BACKEND_API_PORT")) is not None else 8000
    uvicorn.run(app, port=port)


if __name__ == "__main__":
    main()
