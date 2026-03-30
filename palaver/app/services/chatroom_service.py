import anyio
import asyncio
import re
import uuid

from anyio.streams.memory import MemoryObjectSendStream, MemoryObjectReceiveStream
from datetime import datetime
from loguru import logger
from typing import Iterable

import palaver.app.database.db as db

from palaver.app.agent_router.deterministic import DeterministicRouter
from palaver.app.connection_manager import manager
from palaver.app.dataclasses.chatroom import Chatroom, ChatroomCreate, ChatroomUpdate
from palaver.app.dataclasses.events import AgentResponseCompleteEvent, Event, SendAgentEvent, CoroEvent, AgentFinishedEvent, WebSocketEvent
from palaver.app.dataclasses.message import ChatMessage, Message
from palaver.app.dataclasses.run_deps import RunDeps
from palaver.app.enums import RoleEnum
from palaver.app.models.routing import RouteState
from palaver.app.services.agent_service import get_agent_service
from palaver.app.tools import send_agent_tool, set_recipient_tool
from palaver.app.ws_event_stream import AgentRunWSStream


agent_service = get_agent_service()


def create_chatroom(create_request: ChatroomCreate) -> Chatroom:
    """Create a new chatroom"""
    params = {k: v for k, v in create_request.model_dump().items() if v is not None}
    chatroom = Chatroom.model_validate(params)
    db.save_chatroom(chatroom)
    return chatroom


def get_chatroom(chatroom_id: str) -> Chatroom | None:
    """Get a chatroom by ID"""
    try:
        return db.get_chatroom(chatroom_id)
    except ValueError:
        logger.warning(f"Could not find chatroom with id '{chatroom_id}'")


def update_chatroom(chatroom_id: str, update_request: ChatroomUpdate):
    """Get a chatroom by ID"""
    chatroom = get_chatroom(chatroom_id)
    if chatroom is None:
        return
    
    params = chatroom.model_dump() | {k: v for k, v in update_request.model_dump().items() if v is not None}
    new_chatroom = Chatroom.model_validate(params)
    db.save_chatroom(new_chatroom)
    return


def get_all_chatrooms() -> list[Chatroom]:
    """Get all chatrooms"""
    return db.load_chatrooms()


def add_agent_to_chatroom(chatroom_id: str, agent_id: str) -> bool:
    """Add an agent to a chatroom"""
    chatroom = get_chatroom(chatroom_id)
    if chatroom is None:
        return False
    
    chatroom.agents.append(agent_id)
    db.save_chatroom(chatroom)
    return True


def remove_agent_from_chatroom(chatroom_id: str, agent_id: str) -> bool:
    """Remove an agent from a chatroom"""
    chatroom = get_chatroom(chatroom_id)
    if chatroom is None:
        return False

    agents = chatroom.agents
    if agent_id in agents:
        chatroom.agents = [a for a in agents if a != agent_id]
    
    db.save_chatroom(chatroom)
    return True


def get_chatroom_agents(chatroom_id: str) -> list[str]:
    """Get all agents in a chatroom"""
    chatroom = get_chatroom(chatroom_id)
    if chatroom is None:
        return []
    
    return chatroom.agents

   
def filter_target_ids(chatroom_id: str, target_ids: list[str]) -> list[str] | None:
    filtered = []
    chatroom_agent_ids = set(get_chatroom_agents(chatroom_id))
    for target_id in target_ids:
        if target_id not in chatroom_agent_ids or agent_service.get_agent(target_id) is None:
            continue
        filtered.append(target_id)
    return None if not filtered else filtered


def store_chat_message(chatroom_id: str, chat_message: ChatMessage):
    db.save_message(chatroom_id, chat_message)


def create_message(chatroom_id: str, message: Message) -> ChatMessage:
    """Create a new message in a chatroom"""
    message_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    
    chat_message = ChatMessage(
        id=message_id,
        chatroom_id=chatroom_id,
        timestamp=timestamp,
        **message.model_dump(),
    )
    if chat_message.target_agent_ids:
        chat_message.target_agent_ids = filter_target_ids(chatroom_id, chat_message.target_agent_ids)
    store_chat_message(chatroom_id, chat_message)
    
    return chat_message


def get_chatroom_messages(chatroom_id: str, limit: int = None) -> list[ChatMessage]:
    """Get messages from a chatroom"""
    if limit is None:
        return db.load_messages(chatroom_id)
    
    return db.load_messages(chatroom_id)[-limit:]


def extract_target_ids(chatroom_id, agent_id: str, text: str) -> list[str] | None:
    target_ids = []
    pattern = r"@(\w+)"
    for match in re.finditer(pattern, text):
        target_id = match.group(1)
        if target_id != agent_id:
            target_ids.append(match.group(1))
    return filter_target_ids(chatroom_id, target_ids)


def get_largest_subchain(
    agent_chain: tuple[str, ...],
    ref_chains: Iterable[tuple[str, ...]]
) -> tuple[str, ...] | None:
    logger.debug(f"Finding largest subchain for {agent_chain}, {list[ref_chains]}")
    for chain in sorted(ref_chains, key=lambda c: len(c), reverse=True):
        if len(chain) > len(agent_chain):
            return None
        if (subchain := agent_chain[:len(chain)]) == chain:
            logger.debug(f"Found {subchain}")
            return subchain
        logger.debug(f"Found {None}")


def message_agent_event(
        run_deps: RunDeps,
        await_reply: bool,
    ) -> SendAgentEvent:
    chatroom_id = run_deps.chatroom_id
    agent_id = run_deps.agent_id
    user_message = run_deps.user_message
    exclude_agents = run_deps.route_state.agent_chain + (agent_id,)
    other_agent_ids = [aid for aid in get_chatroom_agents(chatroom_id) if aid not in exclude_agents]
    system_prompt = agent_service.create_system_prompt(agent_id, other_agent_ids)
    agent_run_handler = AgentRunWSStream(agent_id)
    if not other_agent_ids:
        tools = None
    else:
        tools = [
            send_agent_tool(
                message_agent_event_func=message_agent_event,
                recipient_verifier=lambda aid: aid in other_agent_ids,
                event_stream_handler=agent_run_handler,
        )]
    logger.debug(f"Tools for {agent_id}: {tools}")

    async def agent_run_coro():
        async with run_deps.send_stream as stream:
            agent = agent_service.agent_manager.get_agent(agent_id)
            await agent_service.agent_manager._agent_run(
                agent=agent,
                message=user_message, 
                chat_history=list(run_deps.chat_history),
                system_prompt=system_prompt,
                run_deps=run_deps,
                tools=tools,
                event_stream_handler=agent_run_handler.event_handler
            )
            logger.debug(f"Awaiting sending AgentFinishedEvent for {agent_id}")
            await stream.send(AgentFinishedEvent(run_deps.await_id_chain))
            logger.debug(f"Sent AgentFinishedEvent for {agent_id}")

    coro = agent_run_coro()
    return SendAgentEvent(
        coro,
        await_id_chain=run_deps.await_id_chain,
        is_awaited=await_reply
    )


async def start_agent_loop(
        chatroom_id: str,
        agent_id: str,
        user_message: Message,
        chat_history: list[ChatMessage],
        send_stream: MemoryObjectSendStream[Event],
    ):
    chatroom = get_chatroom(chatroom_id)
    route_state = RouteState(
        router_type=chatroom.router_type,
        agent_chain=(agent_id,)
    )
    run_deps = RunDeps(
        chatroom_id=chatroom_id,
        agent_id=agent_id,
        route_state=route_state,
        user_message=user_message,
        send_stream=send_stream.clone(),
        chat_history=tuple(chat_history),
        max_subagent_calls=chatroom.max_chain_depth,
    )
    event = message_agent_event(run_deps, False)
    async with send_stream:
        await send_stream.send(event)


async def iterate_agent_loop(chatroom_id: str, receive_stream: MemoryObjectReceiveStream[Event]):
    awaiting_events = dict()
    async with receive_stream:
        async with anyio.create_task_group() as tg:
            async for event in receive_stream:
                if isinstance(event, CoroEvent):
                    tg.start_soon(event)
                    logger.debug("Launched CoroEvent")

                if isinstance(event, WebSocketEvent):
                    await manager.broadcast(event.model_dump_json(exclude={"agent_chain"}), chatroom_id)
                
                if isinstance(event, SendAgentEvent):
                    logger.debug(f"Processing SendAgentEvent(agent_chain={event.await_id_chain}, is_awaited={event.is_awaited})")
                    if event.is_awaited:
                        agent_chain = event.await_id_chain
                        awaiting_events[agent_chain] = {
                            "event": event,
                            "still_awaits": 1,
                            "received_replies": []
                        }
                    elif awaiting_events and (
                            subchain := get_largest_subchain(
                            event.await_id_chain, awaiting_events.keys()
                        )) is not None:
                        awaiting_events[subchain]["still_awaits"] += 1

                elif isinstance(event, AgentFinishedEvent):
                    logger.debug(f"AgentFinishedEvent received for {event.await_id_chain}")
                    if not awaiting_events:
                        continue
                    logger.debug(awaiting_events)
                    subchain = get_largest_subchain(
                            event.await_id_chain, awaiting_events.keys()
                        )
                    awaiting = awaiting_events.get(subchain, None)
                    if awaiting is not None:
                        if awaiting["still_awaits"] > 1:
                            awaiting["still_awaits"] -= 1
                        else:
                            result = "\n".join(awaiting["received_replies"])
                            logger.debug(f"Setting result for chain{event.await_id_chain}")
                            awaiting["event"].set_result(result)
                            awaiting_events.pop(event.await_id_chain)

                elif isinstance(event, AgentResponseCompleteEvent) and event.store_message:
                    if event.recipient == "USER" and awaiting_events and (
                            subchain := get_largest_subchain(
                            event.await_id_chain, awaiting_events.keys()
                        )) is not None:
                        reply = f"{event.agent_id}: {event.content}"
                        logger.debug(f"Adding reply to {subchain} '{reply}'")
                        awaiting_events[subchain]["received_replies"].append(reply)
                    
                    if event.store_message:
                        timestamp = datetime.now().isoformat()
                        reply_message = ChatMessage(
                            id=event.message_id,
                            chatroom_id=chatroom_id,
                            sender=event.agent_id,
                            role=RoleEnum.ASSISTANT,
                            content=event.content,
                            timestamp=timestamp,
                            target_agent_ids=[event.recipient],
                        )
                        store_chat_message(chatroom_id, reply_message)

            logger.debug("No more events received")


async def run_agent_loop(
        chatroom_id: str,
        agent_id: str,
        user_message: Message,
        chat_history: list[ChatMessage],
    ):
    send_stream, receive_stream = anyio.create_memory_object_stream[Event]()
    async with anyio.create_task_group() as tg:
        tg.start_soon(
            start_agent_loop,
            chatroom_id,
            agent_id,
            user_message,
            chat_history,
            send_stream,
        )
        tg.start_soon(
            iterate_agent_loop,
            chatroom_id,
            receive_stream
        )


async def generate_agent_response_streaming(
        chatroom_id: str,
        agent_id: str,
        user_message: Message,
        chat_history: list[ChatMessage],
        route_state: RouteState = None,
    ) -> str:
    """
    Generate a response from an agent, stream tokens via WebSocket, and persist the final message.
    """
    chatroom = get_chatroom(chatroom_id)
    other_agent_ids = [aid for aid in get_chatroom_agents(chatroom_id) if aid != agent_id]
    system_prompt = agent_service.create_system_prompt(agent_id, other_agent_ids)
    route_state = RouteState(
        router_type=chatroom.router_type
    ) if route_state is None else route_state
    run_deps = RunDeps(
        chatroom_id=chatroom_id,
        agent_id=agent_id,
        route_state=route_state,
        user_message=user_message,
        chat_history=tuple(chat_history),
        max_subagent_calls=chatroom.max_chain_depth,
    )
    
    curr_response = ""
    tasks = []
    async for event in agent_service.stream_agent_events(
        agent_id=agent_id, 
        message=user_message, 
        chat_history=chat_history,
        system_prompt=system_prompt,
        run_deps=run_deps,
        tools=[
            set_recipient_tool(chatroom.agents)
            # send_agent_tool(
            #     messaging_func=generate_agent_response_streaming,
            #     recipient_verifier=lambda aid: aid in get_chatroom_agents(chatroom_id))
            ]
    ):
        await manager.broadcast(event.model_dump_json(), chatroom_id)
        if isinstance(event, AgentResponseCompleteEvent):
            curr_response = event.content
            timestamp = datetime.now().isoformat()
            reply_message = ChatMessage(
                id=event.message_id,
                chatroom_id=chatroom_id,
                sender=event.agent_id,
                role=RoleEnum.ASSISTANT,
                content=curr_response,
                timestamp=timestamp,
                target_agent_ids=[event.recipient],
            )
            store_chat_message(chatroom_id, reply_message)

            if event.recipient != "USER" and run_deps.allows_agent_messaging:
                user_chat_message = ChatMessage(
                    **user_message.model_dump(),
                    id="inner_chain_message",
                    chatroom_id=chatroom_id,
                    timestamp=""
                )
                chat_history += [user_chat_message]
                agent_message = reply_message.to_message()
                agent_message.role = RoleEnum.AGENT
                route_state = DeterministicRouter.update_state(
                    route_state, agent_id
                )
                loop = asyncio.get_event_loop()
                task = loop.create_task(
                    generate_agent_response_streaming(
                        chatroom_id=chatroom_id,
                        agent_id=event.recipient,
                        user_message=agent_message,
                        chat_history=chat_history,
                        route_state=run_deps.route_state,
                    )
                )
                tasks.append(task)
        
    async def _inner_generator():
        yield curr_response
        await asyncio.gather(*tasks)

    return await anext(_inner_generator())