from __future__ import annotations

import json
import time
import uuid

from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context, session

from app.ai_calls import call_ai
from app.terminal_manager import TerminalManager
from app.terminal_pip import (
    _SESSION_PIP_REQUIREMENTS_KEY,
    merge_pip_requirements,
    pip_install_requirements_into_session_sandbox,
)

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
    editor_content = payload.get("editorContent") or ""
    displayed_url = payload.get("displayedUrl") or payload.get("displayedURL") or ""

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

    # placeholder for pip requirements
    pip_requirements = ['cowsay']
    # note: struggles with torch due to space requirements from cuda packages
    # should probably be handled by the AI agent.

    browser_id = str(session.get("browser_id") or "").strip()
    sandbox_id_for_session = (
        TerminalManager.get_active_sandbox_id(browser_id=browser_id) if browser_id else None
    )
    if True:
        # Debug-only: install into the current browser session's E2B sandbox.
        sandbox_id = sandbox_id_for_session or ""
        print('sandbox_id', sandbox_id)
        if isinstance(sandbox_id, str) and sandbox_id.strip():
            if isinstance(pip_requirements, str):
                req_lines = [ln.strip() for ln in pip_requirements.splitlines()]
            else:
                req_lines = list(pip_requirements or [])

            result, err2, status = pip_install_requirements_into_session_sandbox(
                sandbox_id=str(sandbox_id),
                requirements=req_lines,
            )
            print('result')
            if err2 is not None:
                raise RuntimeError(f"pip install failed ({status}): {err2}")
            assert result is not None
            normalized = result.get("normalized_requirements", None)
            if isinstance(normalized, list) and all(isinstance(x, str) for x in normalized):
                session[_SESSION_PIP_REQUIREMENTS_KEY] = merge_pip_requirements(
                    session.get(_SESSION_PIP_REQUIREMENTS_KEY), normalized
                )

    def generate():
        message_id = str(uuid.uuid4())
        text_id = "assistant-text-1"

        yield _ndjson_line(
            {
                "type": "start",
                "messageId": message_id,
            }
        )

        # Send UI state separately from text deltas to keep the streaming protocol lean.
        yield _ndjson_line(
            {
                "type": "ui-state",
                "editorContent": editor_content,
                "displayedUrl": documentation_url,
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
