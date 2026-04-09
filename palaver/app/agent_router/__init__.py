from palaver.app.agent_loop.stream_session import StreamSession
from palaver.app.agent_router.base import RouterPolicy
from palaver.app.agent_router.autonomous import AutonomousRouterPolicy
from palaver.app.enums import RoutingType


def get_router_policy(
        router_type: RoutingType,
        agent_id: str,
        other_agent_ids: str,
        stream_session: StreamSession,
    ) -> RouterPolicy:
    if router_type == RoutingType.AUTONOMOUS:
        return AutonomousRouterPolicy(agent_id, other_agent_ids, stream_session)

    # Placeholder fallback until dedicated strategies are implemented.

    return AutonomousRouterPolicy(agent_id, other_agent_ids, stream_session)
