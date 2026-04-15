from palaver.app.agent_loop.stream_session import StreamSession
from palaver.app.agent_router.autonomous import AutonomousRouterPolicy
from palaver.app.agent_router.base import RouterPolicy
from palaver.app.agent_router.incognito import IncognitoRouterPolicy
from palaver.app.agent_router.round_robin import RoundRobinRouterPolicy
from palaver.app.agent_router.single import SingleAgentRouterPolicy
from palaver.app.dataclasses.agent import AgentInfo
from palaver.app.enums import RoutingType


def get_router_policy(
        router_type: RoutingType,
        active_agent_id: str,
        available_agent_ids: list[str],
        parent_agent_ids: tuple[str, ...],
        agent_infos: list[AgentInfo],
        stream_session: StreamSession,
    ) -> RouterPolicy:
    params = dict(
        active_agent_id=active_agent_id,
        available_agent_ids=available_agent_ids,
        parent_agent_ids=parent_agent_ids,
        agent_infos=agent_infos,
        stream_session=stream_session,
    )
    if router_type == RoutingType.AUTONOMOUS:
        return AutonomousRouterPolicy(**params)
    elif router_type == RoutingType.ROUND_ROBIN:
        return RoundRobinRouterPolicy(**params)
    elif router_type == RoutingType.SINGLE:
        return SingleAgentRouterPolicy(**params)
    elif router_type == RoutingType.INCOGNITO:
        return IncognitoRouterPolicy(**params)
    raise ValueError(f"Invalid router type '{router_type}'")
