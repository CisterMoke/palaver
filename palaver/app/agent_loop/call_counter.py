from pydantic import BaseModel

from palaver.app.exceptions import TooManyCalls

class CallCounter(BaseModel):
    max_calls: int | None = None
    value: int = 0

    @property
    def calls_at_limit(self):
        return self.max_calls is not None and self.value >= self.max_calls

    @property
    def calls_exceeded(self) -> bool:
        return self.max_calls is not None and self.value > self.max_calls

    def add(self, num: int = 1):
        self.value += num
        if self.calls_exceeded:
            raise TooManyCalls("Maximum number of calls exceeded")

    # def __eq__(self, value) -> bool:
    #     return self.value == value

    # def __gt__(self, other):
    #     return self.value > other

    # def __lt__(self, other):
    #     return self.value < other

    # def __ge__(self, other):
    #     return self.__gt__(other) or self.__eq__(other)

    # def __le__(self, other):
    #     return self.__lt__(other) or self.__eq__(other)