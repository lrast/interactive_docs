import os

from pydantic_ai import Agent

from pathlib import Path
from pydantic import BaseModel
from pydantic_ai.messages import ModelMessagesTypeAdapter


_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
system_prompt = (_PROMPTS_DIR / "system_prompt.txt").read_text(encoding="utf-8")
user_prompt_template = (_PROMPTS_DIR / "user_prompt_wrapper.txt").read_text(encoding="utf-8")


class AiReply(BaseModel):
    """ AI model response constraint """
    response: str
    editor_content: str = ""
    documentation_url: str = ""
    pip_requirements: list = []


agent = Agent('openai:gpt-5.2', instructions=system_prompt,
              output_type=AiReply
              )


def _load_message_history(session: dict):
    raw = session.get("message_history")
    if not raw:
        return []
    try:
        return ModelMessagesTypeAdapter.validate_python(raw)
    except Exception:
        # If we ever change formats, don't hard-fail the chat endpoint.
        return []


def _dump_message_history(messages) -> list[dict]:
    return ModelMessagesTypeAdapter.dump_python(messages, mode="json")


def _cap_message_history(messages, max_messages: int):
    if max_messages <= 0:
        return messages
    try:
        return messages[-max_messages:]
    except Exception:
        return messages


def call_ai(user_input: dict, session: dict) -> AiReply:
    """ Handler for AI agent calls"""
    user_prompt = user_prompt_template.format(**user_input)

    message_history = _load_message_history(session)
    result = agent.run_sync(user_prompt, message_history=message_history)

    try:
        max_messages = int(os.environ.get("MAX_HISTORY_MESSAGES", "80"))
    except Exception:
        max_messages = 80

    session["message_history"] = _dump_message_history(
        _cap_message_history(result.all_messages(), max_messages)
    )
    session.modified = True

    return result.output
