import asyncio


from palaver.app.dataclasses.message import ChatMessage, Message


class SendAgentEvent:
    def __init__(
            self,
            recipient: str,
            message: Message,
            chat_history: list[ChatMessage],
            run_id: str,
            agent_chain: tuple[str, ...],
            awaited_by: str = None,
        ):
        self.recipient = recipient
        self.message = message
        self.chat_history = chat_history
        self.run_id = run_id
        self.agent_chain = agent_chain
        self.awaited_by = awaited_by


class AwaitAgentEvent:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self._done = asyncio.Event()
        self._result = None

    def __await__(self):
        yield from self._done.wait().__await__()
        return self._result

    def set_result(self, value):
        self._done.set()
        self._result = value


class AgentFinishedEvent:
    def __init__(self, run_id: str, awaited_by: str, result: str):
        self.run_id = run_id
        self.awaited_by = awaited_by
        self.result = result