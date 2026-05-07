from __future__ import annotations

import json
import time
import uuid

from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from typing import Any

from flask import Blueprint, Response, jsonify, request, stream_with_context, session

from app.ai_calls import call_ai

bp = Blueprint("chat", __name__, url_prefix="/api")

# To replace with response based fall-back
_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_FALLBACK_HTML_PATH = _TEMPLATES_DIR / "fallback.html"
try:
    _FALLBACK_HTML = _FALLBACK_HTML_PATH.read_text(encoding="utf-8")
except Exception as e:
    raise RuntimeError(f"Missing fallback HTML template at {_FALLBACK_HTML_PATH}") from e


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
