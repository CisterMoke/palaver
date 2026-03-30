from pydantic import BaseModel, ConfigDict, Field


from palaver.app.enums import RouterType


class RouteState(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    router_type: RouterType
    agent_chain: tuple[str, ...] = Field(default_factory=tuple)
