from anyio.streams.memory import MemoryObjectSendStream
from pydantic import BaseModel, ConfigDict, Field

from palaver.app.dataclasses.events import Event
from palaver.app.dataclasses.message import ChatMessage, Message
from palaver.app.models.routing import RouteState


class RunDeps(BaseModel):
    class CallCounter(BaseModel):
        value: int = 0

        def add(self, num: int = 1):
            self.value += num

        def __eq__(self, value) -> bool:
            return self.value == value

        def __gt__(self, other):
            return self.value > other

        def __lt__(self, other):
            return self.value < other

        def __ge__(self, other):
            return self.__gt__(other) or self.__eq__(other)

        def __le__(self, other):
            return self.__lt__(other) or self.__eq__(other)
    model_config = ConfigDict(arbitrary_types_allowed=True)

    chatroom_id: str
    agent_id: str
    user_message: Message
    route_state: RouteState
    send_stream: MemoryObjectSendStream[Event]
    chat_history: tuple[ChatMessage, ...] = Field(..., default_factory=tuple)
    max_subagent_calls: int | None = None
    recipient: str = "USER"
    call_counter: CallCounter = Field(..., default_factory=CallCounter)
    await_id_chain: tuple[str, ...] = Field(..., default_factory=tuple)

    @property
    def allows_agent_messaging(self):
        return self.max_subagent_calls is None or len(self.route_state.agent_chain) < self.max_subagent_calls