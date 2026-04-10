from palaver.app.agent_loop.stream_session import StreamSession
from palaver.app.agent_router.base import RouterPolicy
from palaver.app.agent_router.autonomous import AutonomousRouterPolicy
from palaver.app.agent_router.round_robin import RoundRobinRouterPolicy
from palaver.app.enums import RoutingType


def get_router_policy(
        router_type: RoutingType,
        active_agent_id: str,
        available_agent_ids: list[str],
        parent_agent_ids: tuple[str, ...],
        stream_session: StreamSession,
    ) -> RouterPolicy:
    if router_type == RoutingType.AUTONOMOUS:
        return AutonomousRouterPolicy(active_agent_id, available_agent_ids, parent_agent_ids, stream_session)
    elif router_type == RoutingType.ROUND_ROBIN:
        return RoundRobinRouterPolicy(active_agent_id, available_agent_ids, parent_agent_ids, stream_session)
    raise ValueError(f"Invalid router type '{router_type}'")
