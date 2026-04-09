
import datetime

from loguru import logger

from palaver.app.database import db
from palaver.app.enums import RoleEnum
from palaver.app.event_handlers.base import BaseEventHandler
from palaver.app.events.ui import AgentResponseCompleteEvent, UIEvent
from palaver.app.dataclasses.message import ChatMessage
from palaver.app.websocket_manager import get_ws_manager


class ChatroomEventHandler(BaseEventHandler):
    def __init__(self, chatroom_id: str):
        self.chatroom_id = chatroom_id
        self.ws_manager = get_ws_manager()

    async def handle_event(self, event):
        if isinstance(event, UIEvent):
            if event.type != "agent_response_chunk":
                logger.debug(f"Broadcasting event '{event.type}'")
            await self.ws_manager.broadcast(
                event.model_dump_json(exclude={"agent_chain"}), self.chatroom_id
            )

        if isinstance(event, AgentResponseCompleteEvent):
            self._store_agent_response(event)

    def _store_agent_response(self, event: AgentResponseCompleteEvent) -> None:
        timestamp = datetime.datetime.now().isoformat()
        reply_message = ChatMessage(
            id=event.message_id,
            chatroom_id=self.chatroom_id,
            sender=event.agent_id,
            role=RoleEnum.ASSISTANT,
            content=event.content,
            timestamp=timestamp,
            recipients=[event.recipient],
        )
        db.save_message(self.chatroom_id, reply_message)
