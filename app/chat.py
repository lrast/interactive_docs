from __future__ import annotations

import json
import time
import uuid

from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
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

# To replace with response based fall-back
_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_FALLBACK_HTML_PATH = _TEMPLATES_DIR / "fallback.html"
try:
    _FALLBACK_HTML = _FALLBACK_HTML_PATH.read_text(encoding="utf-8")
except Exception as e:
    raise RuntimeError(f"Missing fallback HTML template at {_FALLBACK_HTML_PATH}") from e


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

    print(documentation_url)

    # install pip requirements into the sandbox if running in e2b
    # note: struggles with torch due to space requirements from cuda packages
    # this should probably be handled by the AI agent.

    browser_id = str(session.get("browser_id") or "").strip()
    sandbox_id_for_session = (
        TerminalManager.get_active_sandbox_id(browser_id=browser_id) if browser_id else None
    )
    terminal_provider = str(current_app.config["TERMINAL_PROVIDER"]).strip().lower()

    if terminal_provider in ("e2b", "e2b-sandbox"):
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

    use_fallback = not _is_embeddable_url(documentation_url)

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
                "fallbackHtml": _FALLBACK_HTML,
                "useFallback": use_fallback,
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
                "fallbackHtml": _FALLBACK_HTML,
                "useFallback": use_fallback,
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


# Helpers: checking whether the link can be shown in an iframe

def _parse_csp_frame_ancestors(csp_header: str) -> list[str] | None:
    if not csp_header:
        return None
    directives = [d.strip() for d in csp_header.split(";") if d.strip()]
    for d in directives:
        if d.lower().startswith("frame-ancestors"):
            parts = d.split()
            return [p.strip() for p in parts[1:]]
    return None


def _is_embeddable_url(url: str) -> bool:
    if not isinstance(url, str) or not url.strip():
        return False
    url = url.strip()

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False

    req = Request(
        url,
        method="HEAD",
        headers={
            "User-Agent": "interactive-docs/1.0 (+iframe-embeddability-preflight)",
            "Accept": "*/*",
        },
    )

    try:
        with urlopen(req, timeout=2.0) as resp:
            headers = resp.headers
    except HTTPError:
        return False
    except URLError:
        return False
    except Exception:
        return False

    xfo = (headers.get("X-Frame-Options") or "").strip().lower()
    if xfo:
        if "deny" in xfo:
            return False
        if "sameorigin" in xfo:
            return False

    csp = headers.get("Content-Security-Policy") or headers.get(
        "Content-Security-Policy-Report-Only"
    )
    frame_ancestors = _parse_csp_frame_ancestors(csp or "")
    if frame_ancestors is not None:
        toks = [t.strip() for t in frame_ancestors if t.strip()]
        lower = [t.lower() for t in toks]

        if "'none'" in lower:
            return False
        if "*" in toks:
            return True

        return False

    return True
