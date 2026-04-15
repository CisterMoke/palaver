from enum import StrEnum


class RoleEnum(StrEnum):
    AGENT = "agent"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    USER = "user"


class RoutingType(StrEnum):
    AUTONOMOUS = "autonomous"
    ROUND_ROBIN = "round_robin"
    SINGLE = "single"
    INCOGNITO = "incognito"