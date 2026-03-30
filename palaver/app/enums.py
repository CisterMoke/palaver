from enum import StrEnum


class RoleEnum(StrEnum):
    AGENT = "agent"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    USER = "user"


class RouterType(StrEnum):
    DETERMINISTIC = "deterministic"
    RANDOM = "random"