from pathlib import Path

from palaver.app.dataclasses.llm import ChatroomMessage

with open(Path(__file__).parent / "base_prompt.txt") as f:
    BASE_PROMPT = f.read().replace("[[chatroom_message_schema]]", str(ChatroomMessage.model_json_schema()))