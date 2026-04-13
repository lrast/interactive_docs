from __future__ import annotations

import json
import time
import uuid
from typing import Any

from flask import Blueprint, Response, request, stream_with_context

bp = Blueprint("chat", __name__, url_prefix="/api")


def _text_from_parts(parts: list[Any] | None) -> str:
    if not parts:
        return ""
    out: list[str] = []
    for p in parts:
        if isinstance(p, dict) and p.get("type") == "text":
            out.append(str(p.get("text", "")))
    return "".join(out).strip()


def _ndjson_line(obj: dict) -> str:
    return json.dumps(obj, separators=(",", ":")) + "\n"


@bp.post("/chat")
def chat_stream():
    payload = request.get_json(silent=True) or {}
    message = payload.get("message") or {}
    user_text = _text_from_parts(message.get("parts"))

    def generate():
        message_id = str(uuid.uuid4())
        text_id = "assistant-text-1"
        yield _ndjson_line({"type": "start", "messageId": message_id})
        reply = (
            "Stub assistant: streaming from Flask. You said: "
            + (user_text[:800] if user_text else "(empty message)")
        )
        step = 6
        for i in range(0, len(reply), step):
            chunk = reply[i : i + step]
            yield _ndjson_line({"type": "text-delta", "id": text_id, "delta": chunk})
            time.sleep(0.04)
        yield _ndjson_line({"type": "text-end", "id": text_id})
        yield _ndjson_line({"type": "finish", "messageId": message_id})

    return Response(
        stream_with_context(generate()),
        mimetype="application/x-ndjson; charset=utf-8",
    )
