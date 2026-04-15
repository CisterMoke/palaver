from pathlib import Path

from palaver.app.dataclasses.llm import ChatroomMessage, IncognitoMessage

with open(Path(__file__).parent / "base_prompt.txt") as f:
    BASE_PROMPT = f.read().replace("[[chatroom_message_schema]]", str(ChatroomMessage.model_json_schema()))

with open(Path(__file__).parent / "incognito_prompt.txt") as f:
    INCOGNITO_PROMPT = f.read().replace("[[incognito_message_schema]]", str(IncognitoMessage.model_json_schema()))