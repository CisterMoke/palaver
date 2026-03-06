import json

from fastapi import WebSocket
from typing import Any


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}  # chatroom_id -> [WebSocket]

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
            for connection in self.active_connections[chatroom_id]:
                await connection.send_text(message)

    async def broadcast_json(self, data: dict[str, Any], chatroom_id: str):
        """Broadcast a dict as JSON to all connections in a chatroom."""
        await self.broadcast(json.dumps(data), chatroom_id)


manager = ConnectionManager()
