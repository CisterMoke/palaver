from anyio.streams.memory import MemoryObjectSendStream

from palaver.app.events import Event


class StreamSession:
    def __init__(self, send_stream: MemoryObjectSendStream[Event]):
        self._send_stream = send_stream

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._send_stream.aclose()

    def get_stream(self):
        return self._send_stream.clone()