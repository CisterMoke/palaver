import abc



class BaseEventHandler(abc.ABC):

    @abc.abstractmethod
    def handle_event(cls, event):
        ...