from palaver.app.enums import AgentLoopStatus
from palaver.app.events.base import Event


class AgentLoopEvent(Event):
    def __init__(self, status: AgentLoopStatus):
        self.status = status


class RemoveAgentEvent(Event):
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
