from palaver.app.events.base import Event


class SystemMessageEvent(Event):
    ...


class RemoveAgentEvent(Event):
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        