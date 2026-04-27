from __future__ import annotations

import json
import time
import uuid

from typing import Any

from flask import Blueprint, Response, jsonify, request, stream_with_context, session

from app.ai_calls import call_ai

bp = Blueprint("chat", __name__, url_prefix="/api")

@bp.get("/session")
def browser_session():
    """Stable per-browser id (signed cookie session). Used for server-side scoping."""
    return jsonify({"browserSessionId": session.get("browser_id")})


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
    user_message = _text_from_parts(message.get("parts"))

    # Wire schema uses camelCase; backend uses snake_case internally.
    # We keep fallbacks for older clients during the transition.
    editor_content = payload.get("editorContent") or ""
    displayed_url = payload.get("displayedUrl") or payload.get("displayedURL") or ""

    # IMPORTANT: This endpoint streams. The session cookie can only be set in headers,
    # so we must call the AI (which mutates `session`) BEFORE we yield any bytes.
    reply = call_ai(
        {
            "user_message": user_message,
            "editor_content": editor_content,
            "displayed_url": displayed_url,
        },
        session,
    )

    response = reply.response
    editor_content = reply.editor_content
    documentation_url = reply.documentation_url

    def generate():
        message_id = str(uuid.uuid4())
        text_id = "assistant-text-1"

        yield _ndjson_line(
            {
                "type": "start",
                "messageId": message_id,
            }
        )

        step = 6
        for i in range(0, len(response), step):
            chunk = response[i: i + step]
            yield _ndjson_line(
                {
                    "type": "text-delta",
                    "id": text_id,
                    "delta": chunk,
                    "editorContent": editor_content,
                    "displayedUrl": documentation_url,
                }
            )
            time.sleep(0.04)
        yield _ndjson_line({"type": "text-end", "id": text_id})
        yield _ndjson_line(
            {
                "type": "finish",
                "messageId": message_id,
                "editorContent": editor_content,
                "displayedUrl": documentation_url,
            }
        )

    return Response(
        stream_with_context(generate()),
        mimetype="application/x-ndjson; charset=utf-8",
    )
