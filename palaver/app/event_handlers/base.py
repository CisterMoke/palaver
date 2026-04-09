import abc

from palaver.app.events import Event


class BaseEventHandler(abc.ABC):

    @abc.abstractmethod
    def handle_event(cls, event):
        ...