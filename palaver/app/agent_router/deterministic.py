from palaver.app.models.routing import RouteState


class DeterministicRouter:
    @classmethod
    def update_state(
        cls,
        route_state: RouteState,
        recipient: str,
    ) -> RouteState:
        new_chain = route_state.agent_chain +  (recipient,)
        new_state = RouteState(
            **route_state.model_dump(exclude={"agent_chain"}),
            agent_chain=new_chain,
        )
        return new_state