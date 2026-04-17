import anyio

from fastapi import WebSocket
from functools import lru_cache
from pydantic import BaseModel
from pydantic_core import to_jsonable_python
from typing import Any


class WebSocketManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, chatroom_id: str):
        await websocket.accept()
        if chatroom_id not in self.active_connections:
            self.active_connections[chatroom_id] = []
        self.active_connections[chatroom_id].append(websocket)

    def disconnect(self, websocket: WebSocket, chatroom_id: str):
        if chatroom_id in self.active_connections:
            self.active_connections[chatroom_id].remove(websocket)
            if not self.active_connections[chatroom_id]:
                del self.active_connections[chatroom_id]
    
    async def broadcast(self, message: str, chatroom_id: str):
        if chatroom_id in self.active_connections:
            async with anyio.create_task_group() as tg:
                for conn in self.active_connections[chatroom_id]:
                    tg.start_soon(conn.send_text, message)

    async def broadcast_json(self, data: dict[str, Any], chatroom_id: str):
        if chatroom_id in self.active_connections:
            async with anyio.create_task_group() as tg:
                for conn in self.active_connections[chatroom_id]:
                    tg.start_soon(conn.send_json, data)

    async def broadcast_model(self, model: BaseModel, chatroom_id: str):
        await self.broadcast_json(to_jsonable_python(model), chatroom_id)



@lru_cache
def get_ws_manager():
    return WebSocketManager()
