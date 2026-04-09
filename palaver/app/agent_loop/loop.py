import anyio
import uuid

from loguru import logger
from pydantic_ai.capabilities import Hooks

from palaver.app.agent_loop.call_counter import CallCounter
from palaver.app.agent_loop.stream_session import StreamSession
from palaver.app.agent_router import get_router_policy
from palaver.app.config import AgentLoopConfig
from palaver.app.dataclasses.message import ChatMessage, Message
from palaver.app.dataclasses.run_deps import RunDeps
from palaver.app.event_bridges.base import BaseEventBridge
from palaver.app.event_bridges.core import CoreEventBridge
from palaver.app.event_handlers.base import BaseEventHandler
from palaver.app.event_handlers.core import CoreEventHandler
from palaver.app.events import Event
from palaver.app.events.agent import SendAgentEvent, AgentFinishedEvent, AwaitAgentEvent
from palaver.app.events.ui import AgentResponseErrorEvent
from palaver.app.models.agent import Agent
from palaver.app.services.agent_service import AgentManager


class AgentLoop:
    def __init__(self, agents: list[Agent], config: AgentLoopConfig):
        self.config = config
        send_stream, self.receive_stream = anyio.create_memory_object_stream[Event]()
        self.send_stream_session = StreamSession(send_stream)
        self.call_counter = CallCounter(max_calls=config.max_subagent_calls)
        self.agent_manager = AgentManager(agents)
        self.event_bridges: list[type[BaseEventBridge]] = [CoreEventBridge]
        self.event_handlers: list[BaseEventHandler] = [CoreEventHandler()]
    
    @property
    def subagent_calls(self):
        return self.call_counter.value()
    
    def add_event_bridge(self, bridge_class: type[BaseEventBridge]):
        self.event_bridges.append(bridge_class)
    
    def add_event_handler(self, event_handler: BaseEventHandler):
        self.event_handlers.append(event_handler)

    def _init_hooks(self, agent_id: str) -> list[Hooks[RunDeps]]:
        hooks = []
        for bridge_class in self.event_bridges:
            instance = bridge_class(agent_id=agent_id, stream_session=self.send_stream_session)
            hooks.append(instance.build_hooks())
        return hooks

    async def message_agent(
            self,
            agent_id: str,
            user_message: Message,
            chat_history: list[ChatMessage],
            run_id: str = None,
            agent_chain: tuple[str, ...] = None,
            awaited_by: str = None
        ):
        if agent_id not in self.agent_manager.agents:
            raise ValueError(f"Agent '{agent_id}' not found")
        
        agent_chain = tuple() if agent_chain is None else agent_chain
        exclude_agents = agent_chain + (agent_id,)
        other_agent_ids = [
            aid for aid in self.agent_manager.agents if aid not in exclude_agents
        ]
        router_policy = get_router_policy(
            router_type=self.config.agent_routing,
            agent_id=agent_id,
            other_agent_ids=other_agent_ids,
            stream_session=self.send_stream_session,
        )
        system_prompt = self.agent_manager.create_system_prompt(
            agent_id,
            other_agent_ids,
        )
        capabilities = self._init_hooks(agent_id)
        capabilities += router_policy.build_capabilities(exclude_tools=self.call_counter.calls_at_limit)

        run_id = str(uuid.uuid4()) if run_id is None else run_id
        chat_history = tuple(chat_history[:self.config.max_message_history])
        run_deps = RunDeps(
            agent_id=agent_id,
            user_message=user_message,
            chat_history=chat_history,
            run_id=run_id,
            call_counter=self.call_counter,
            agent_chain=agent_chain + (agent_id,),
            awaited_by=awaited_by,
        )

        agent = self.agent_manager.get_agent(agent_id)
        agent.capabilities = capabilities
        logger.debug(f"Agent {agent_id} capabilities: {agent.capabilities}, _inner: {agent._inner}")
        
        async def event_stream_handler(ctx, stream):
            async for _event in stream:
                ...
        
        await self.agent_manager._agent_run(
            agent=agent,
            message=user_message,
            chat_history=list(run_deps.chat_history),
            system_prompt=system_prompt,
            run_deps=run_deps,
            event_stream_handler=event_stream_handler,
        )
    
    async def handle_send_agent_event(self, event: SendAgentEvent):
        async with self.send_stream_session.get_stream() as stream:
            try:
                await self.message_agent(
                    agent_id=event.recipient,
                    user_message=event.message,
                    chat_history=event.chat_history,
                    run_id=event.run_id,
                    agent_chain=event.agent_chain,
                    awaited_by=event.awaited_by,
                )
            except Exception as exc:
                await stream.send(
                    AgentResponseErrorEvent(
                        agent_id=event.recipient,
                        error=str(exc),
                    )
                )
                await stream.send(
                    AgentFinishedEvent(
                        run_id=event.run_id,
                        awaited_by=event.awaited_by,
                        result=f"Received {type(exc).__name__}: {exc}",
                    )
                )

    async def start(self, agent_id: str, user_message: Message, chat_history: list[ChatMessage]):
        logger.debug("Starting Main Agent Loop.")
        async with self.send_stream_session as session:
            async with session.get_stream() as stream:
                await_event = AwaitAgentEvent("root")
                await stream.send(await_event)
                send_event = SendAgentEvent(
                    recipient=agent_id,
                    message=user_message,
                    chat_history=chat_history,
                    run_id=str(uuid.uuid4()),
                    agent_chain=None,
                    awaited_by="root",
                )
                await stream.send(send_event)
                await await_event
                # await self.message_agent(agent_id, user_message, chat_history)

    async def iterate(self):
        logger.debug("Iterating Agent Events")
        async with self.receive_stream:
            async with anyio.create_task_group() as tg:
                async for event in self.receive_stream:
                    if isinstance(event, SendAgentEvent):
                        logger.debug(f"Main loop received SendAgentEvent '{event.run_id}'")
                        tg.start_soon(self.handle_send_agent_event, event)
                    elif isinstance(event, AgentFinishedEvent):
                        logger.debug(f"Main loop received AgentFinishedEvent '{event.run_id}'")
                    for handler in self.event_handlers:
                        tg.start_soon(handler.handle_event, event)

        logger.debug("No more events received")

    async def run(self, agent_id: str, user_message: Message, chat_history: list[ChatMessage]):
        async with anyio.create_task_group() as tg:
            tg.start_soon(
                self.start,
                agent_id,
                user_message,
                chat_history,
            )
            tg.start_soon(self.iterate)
