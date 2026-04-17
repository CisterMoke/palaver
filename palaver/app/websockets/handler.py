import anyio

from typing import Any

import palaver.app.services.chatroom_service as cs

from palaver.app.dataclasses.message import IncomingMessage
from palaver.app.events.ui import ChatMessageEvent, CommandResultEvent
from palaver.app.websockets.manager import WebSocketManager


class WebSocketHandler:
    def __init__(self, ws_manager: WebSocketManager, chatroom_id: str):
        self.ws_manager = ws_manager
        self.chatroom_id = chatroom_id

    async def handle_message(self, message: IncomingMessage):
        chatroom = cs.get_chatroom(self.chatroom_id)
        chat_history = cs.get_chatroom_messages(
            self.chatroom_id, limit=chatroom.max_message_history
        )
        stored_message = cs.create_message(
            chatroom_id=self.chatroom_id, message=message
        )
        await self.ws_manager.broadcast_model(
            ChatMessageEvent.model_validate(stored_message.model_dump()),
            self.chatroom_id,
        )
        async with anyio.create_task_group() as tg:
            for agent_id in stored_message.recipients or chatroom.agents[:1]:
                tg.start_soon(
                    cs.run_agent_loop,
                    self.chatroom_id,
                    agent_id,
                    message,
                    chat_history,
                )

    async def handle_data(self, data: dict[str, Any]):
        if data["type"] == "user_message":
            await self.handle_message(
                message=IncomingMessage.model_validate(data["data"])
            )
            return

        if data["type"] == "slash_command":
            payload = data.get("data", {})
            name = str(payload.get("name", "")).strip()
            result = cs.execute_slash_command(
                chatroom_id=self.chatroom_id,
                name=name,
                args=payload.get("args"),
            )
            await self.ws_manager.broadcast_model(
                CommandResultEvent(
                    name=name,
                    status=result["status"],
                    payload=result.get("payload"),
                    error=result.get("error"),
                ),
                self.chatroom_id,
            )
