from __future__ import annotations

import json
import time
import uuid

from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context, session

from app.ai_calls import call_ai
from app.documentation_display import resolve_documentation_display
from app.terminal_manager import TerminalManager
from app.terminal_pip import (
    _SESSION_PIP_REQUIREMENTS_KEY,
    merge_pip_requirements,
    maybe_install_pip_requirements_for_terminal_session
)

bp = Blueprint("chat", __name__, url_prefix="/api")


@bp.get("/session")
def browser_session():
    """Stable per-browser id (signed cookie session). Used for server-side scoping."""
    return jsonify({"browserSessionId": session.get("browser_id")})


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
    pip_requirements = reply.pip_requirements

    # E2B: install into the session sandbox (when configured + available).

    browser_id = str(session.get("browser_id") or "").strip()
    sandbox_id_for_session = (
        TerminalManager.get_active_sandbox_id(browser_id=browser_id) if browser_id else None
    )
    terminal_provider = str(current_app.config["TERMINAL_PROVIDER"]).strip().lower()
    normalized, err2, status = maybe_install_pip_requirements_for_terminal_session(
        terminal_provider=terminal_provider,
        sandbox_id=sandbox_id_for_session,
        pip_requirements=pip_requirements,
    )
    flash_message: str | None = None
    if err2 is not None:
        flash_message = "pip install failed"
    if isinstance(normalized, list) and all(isinstance(x, str) for x in normalized):
        session[_SESSION_PIP_REQUIREMENTS_KEY] = merge_pip_requirements(
            session.get(_SESSION_PIP_REQUIREMENTS_KEY), normalized
        )

    doc_display = resolve_documentation_display(documentation_url)
    out_url = doc_display.documentation_url
    use_fallback = doc_display.use_fallback
    fallback_html = doc_display.fallback_html

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
                "displayedUrl": out_url,
                "fallbackHtml": fallback_html,
                "useFallback": use_fallback,
                "flashMessage": flash_message,
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
                "displayedUrl": out_url,
                "fallbackHtml": fallback_html,
                "useFallback": use_fallback,
                "flashMessage": flash_message,
            }
        )

    return Response(
        stream_with_context(generate()),
        mimetype="application/x-ndjson; charset=utf-8",
    )


# Helpers: streaming text

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
