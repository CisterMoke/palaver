from loguru import logger

from palaver.app.database import db
from palaver.app.data_utils import create_timestamp
from palaver.app.enums import AgentLoopStatus, RoleEnum
from palaver.app.event_handlers.base import BaseEventHandler
from palaver.app.events.agent import SendAgentEvent, AgentFinishedEvent
from palaver.app.events.system import AgentLoopEvent, RemoveAgentEvent
from palaver.app.events.ui import (
    AgentResponseCompleteEvent,
    UIEvent,
    AgentLoopStartEvent,
    AgentLoopEndEvent,
    AgentStartEvent,
    AgentEndEvent,
    SystemMessageEvent,
)
from palaver.app.dataclasses.message import ChatMessage
from palaver.app.websockets.manager import get_ws_manager


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

        ui_event = None
        if isinstance(event, AgentLoopEvent):
            if event.status == AgentLoopStatus.STARTED:
                ui_event = AgentLoopStartEvent()
            elif event.status == AgentLoopStatus.ENDED:
                ui_event = AgentLoopEndEvent()

        if isinstance(event, SystemMessageEvent):
            self._store_system_message(event)

        if isinstance(event, SendAgentEvent):
            ui_event = AgentStartEvent(agent_id=event.recipient)
        if isinstance(event, AgentFinishedEvent):
            ui_event = AgentEndEvent(agent_id=event.agent_id)
        
        if ui_event is not None:
            await self.ws_manager.broadcast_model(ui_event, self.chatroom_id)

    def _store_agent_response(self, event: AgentResponseCompleteEvent) -> None:
        timestamp = create_timestamp()
        reply_message = ChatMessage(
            id=event.message_id,
            chatroom_id=self.chatroom_id,
            sender=event.agent_id,
            role=RoleEnum.ASSISTANT,
            content=event.content,
            timestamp=timestamp,
            recipients=None if event.recipient is None else [event.recipient],
        )
        db.save_message(self.chatroom_id, reply_message)

    def _store_system_message(self, event: SystemMessageEvent) -> None:
        timestamp = create_timestamp()
        reply_message = ChatMessage(
            id=event.message_id,
            chatroom_id=self.chatroom_id,
            sender="SYSTEM",
            role=RoleEnum.SYSTEM,
            content=event.message,
            timestamp=timestamp,
            recipients=None,
        )
        db.save_message(self.chatroom_id, reply_message)
