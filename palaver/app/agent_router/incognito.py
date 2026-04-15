from collections.abc import Callable
from loguru import logger
from pydantic_ai import RunContext
from pydantic_ai.agent import UserPromptNode
from pydantic_ai.capabilities import AbstractCapability, Hooks, Toolset, ValidatedToolArgs, AgentNode
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ToolCallPart, ModelMessage, ModelRequest, UserPromptPart
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import FunctionToolset
from random import sample

from palaver.app.agent_router.round_robin import RoundRobinRouterPolicy
from palaver.app.dataclasses.run_deps import RunDeps
from palaver.app.dataclasses.llm import ChatroomMessage, IncognitoMessage
from palaver.app.events.system import RemoveAgentEvent
from palaver.app.exceptions import TerminateRun
from palaver.app.prompts import INCOGNITO_PROMPT


class IncognitoRouterPolicy(RoundRobinRouterPolicy):
    def __init__(self, active_agent_id, available_agent_ids, parent_agent_ids, agent_infos, stream_session):
        super().__init__(active_agent_id, available_agent_ids, parent_agent_ids, agent_infos, stream_session)

        orig_ids = self.available_agent_ids + ["USER"]
        anon_ids = self._generate_ids(len(orig_ids))
        self.id_map: dict[str, str] = {
            orig: anon for orig, anon in zip(sample(orig_ids, len(orig_ids)), anon_ids, strict=True)
        }
        self.reverse_id_map: dict[str, str] = {
            v: k for k, v in self.id_map.items()
        }

    @classmethod
    def _extract_chatroom_messages(cls, messages: list[ModelMessage]) -> tuple[list[int], list[ChatroomMessage]]:
        indices, extracted = [], []
        for i, msg in enumerate(messages):
            if not isinstance(msg, ModelRequest) or not isinstance(msg.parts[0], UserPromptPart):
                continue
            parsed = ChatroomMessage.model_validate_json(msg.parts[0].content)
            extracted.append(parsed)
            indices.append(i)
        return indices, extracted

    @classmethod
    def _generate_ids(cls, n: int, offset: int = 0) -> list[str]:
        return [f"USER_{i+1+offset}" for i in range(n)]
    
    def _extend_id_maps(self, chat_history: list[ChatroomMessage]):
        extended = set(msg.sender for msg in chat_history).difference(self.id_map.keys())
        anon_ids = self._generate_ids(len(extended), len(self.id_map))

        self.id_map |= {
            orig: anon for orig, anon in zip(extended, anon_ids, strict=True)
        }
        self.reverse_id_map = {
            v: k for k, v in self.id_map.items()
        }
    
    def _anonymize_message(self, message: ChatroomMessage) -> IncognitoMessage:
        anon_id = self.id_map[message.sender]
        return IncognitoMessage(sender=anon_id, content=message.content)
    
    def build_tools(self) -> list[Callable]:
        async def unmask(user: str) -> str:
            """
            Unmask an anonymous user. If the user is human, you win. If it turns out to be an AI agent, you lose and your session will end.
            Use wisely, you only have one chance.

            Args:
                user (str): The name of the user you wish to unmask.

            Returns:
                str: A message indicating whether or not you've won.

            """
            try:
                success = (self.reverse_id_map[user] == "USER")
            except KeyError as e:
                raise ModelRetry(f"Unknown user '{user}'") from e
            
            return success
            
        return [unmask]

    def build_hooks(self) -> Hooks[RunDeps]:
        hooks = super().build_hooks()

        @hooks.on.before_run
        async def _init_run(ctx: RunContext[RunDeps]):
            indices, chatroom_messages = self._extract_chatroom_messages(ctx.messages)
            self._extend_id_maps(chatroom_messages)

            for i, chat_msg in zip(indices, chatroom_messages, strict=True):
                anon_msg = self._anonymize_message(chat_msg)
                ctx.messages[i] = ModelRequest.user_text_prompt(anon_msg.model_dump_json())

            user_msg = ChatroomMessage.model_validate_json(ctx.prompt)
            ctx.prompt = self._anonymize_message(user_msg).model_dump_json()

        @hooks.on.before_node_run
        async def _overwrite_user_prompt(
            ctx: RunContext[RunDeps],
            node: AgentNode,
        ) -> AgentNode:
            if not isinstance(node, UserPromptNode):
                return node
            
            user_msg = ChatroomMessage.model_validate_json(node.user_prompt)
            node.user_prompt = self._anonymize_message(user_msg).model_dump_json()
            return node
            
        @hooks.on.after_tool_execute(tools=["unmask"])
        async def _handle_tool_call(
            ctx: RunContext[RunDeps],
            *,
            call: ToolCallPart,
            tool_def: ToolDefinition,
            args: ValidatedToolArgs,
            result: str
        ) -> str:
            if result:
                result = "You won! You've successfully unmasked the human user. Now we celebrate!"
                logger.debug(f"Agent '{self.active_agent_id}' successfully unmasked the human!")
                return result
            else:
                async with self.stream_session.get_stream() as stream:
                    await stream.send(RemoveAgentEvent(self.active_agent_id))

                raise TerminateRun(
                    f"Agent '{self.active_agent_id}' failed to unmask the human. It guessed '{self.reverse_id_map[args['user']]}' instead.",
                    f"Terminating run '{self.active_agent_id}'[{ctx.deps.run_id}]"
                )
            
        return hooks

    def build_capabilities(self, exclude_tools = False) -> list[AbstractCapability]:
        hooks = self.build_hooks()
        toolset = Toolset(FunctionToolset(self.build_tools()))
        return [hooks, toolset]


    def create_system_prompt(self) -> str:
        """Build the system prompt"""
        agent = self.agent_infos[self.active_agent_id]
        agent_name = self.id_map[self.active_agent_id]

        other_users = "\n".join(
            [
                f"- {anon_id}: An anonymous user." for anon_id in self.id_map.values()
                if anon_id != agent_name
            ]
        )
        prompt = (
            INCOGNITO_PROMPT.replace("[[agent_name]]", agent_name)
            .replace("[[agent_description]]", agent.description)
            .replace("[[other_users]]", other_users)
            .replace("[[agent_prompt]]", agent.prompt)
        )
        return prompt