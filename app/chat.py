from __future__ import annotations

import json
import time
import uuid
#import aisuite

from typing import Any

from flask import Blueprint, Response, jsonify, request, stream_with_context, session

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
    user_text = _text_from_parts(message.get("parts"))
    editor_content = payload.get("editorContent") or ""

    def generate():
        message_id = str(uuid.uuid4())
        text_id = "assistant-text-1"
        yield _ndjson_line({"type": "start", "messageId": message_id})

        # call aisuite
        #response = aisuite.chat.completions.create(
        #    model="gpt-4o-mini",
        #    messages=[
        #        {"role": "user", "content": user_text},
        #    ],
        #)

        reply = (
            "Stub assistant: streaming from Flask. You said: "
            + (user_text[:800] if user_text else "(empty message)")
            + ' ' + current
        )

        step = 6
        for i in range(0, len(reply), step):
            chunk = reply[i: i + step]
            print("chunk", chunk)
            yield _ndjson_line({"type": "text-delta", "id": text_id, "delta": chunk,
                                "editorContent": editor_content})
            time.sleep(0.04)
        yield _ndjson_line({"type": "text-end", "id": text_id})
        yield _ndjson_line({"type": "finish", "messageId": message_id})

    print('session', session)
    print('request session', request.cookies.get('session'))
    print('browser session', browser_session)

    current = session.get("test") or ""

    session['test'] = current + '_run'
    session.modified = True

    return Response(
        stream_with_context(generate()),
        mimetype="application/x-ndjson; charset=utf-8",
    )
