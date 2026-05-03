from __future__ import annotations

import re
import secrets
import time

from flask import Blueprint, current_app, jsonify, request, session


bp = Blueprint("terminal", __name__, url_prefix="/api/terminal")

_SESSION_PIP_REQUIREMENTS_KEY = "terminal_pip_requirements"
_REQ_LINE_ALLOWED_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-\[\],=<>!~+* ]*$")


def _normalize_pip_requirements(payload: object) -> tuple[list[str] | None, str | None]:
    """Validate and normalize a list of pip requirement spec lines.

    Intentionally conservative: accept simple package specs and version pins,
    but reject pip options, URLs/VCS installs, and multi-line input.
    """
    if not isinstance(payload, dict):
        return None, "Invalid JSON payload."

    reqs = payload.get("requirements", None)
    if reqs is None:
        return None, 'Missing "requirements".'
    if not isinstance(reqs, list):
        return None, '"requirements" must be a list of strings.'

    max_lines = int(current_app.config["TERMINAL_MAX_PIP_REQUIREMENTS_LINES"])
    max_chars = int(current_app.config["TERMINAL_MAX_PIP_REQUIREMENT_LINE_CHARS"])
    if max_lines > 0 and len(reqs) > max_lines:
        return None, f"Too many requirements (max {max_lines})."

    out: list[str] = []
    seen: set[str] = set()
    for raw in reqs:
        if not isinstance(raw, str):
            return None, "Each requirement must be a string."
        line = raw.strip()
        if not line:
            continue
        if max_chars > 0 and len(line) > max_chars:
            return None, f"Requirement too long (max {max_chars} chars)."

        if any(ord(ch) < 32 for ch in line) or "\n" in line or "\r" in line:
            return None, "Invalid requirement (control characters)."

        lowered = line.lower()
        if line.startswith("-") or lowered.startswith("--"):
            return None, "Invalid requirement (pip options are not allowed)."
        if " -r " in f" {lowered} ":
            return None, "Invalid requirement (recursive requirements not allowed)."
        if "://" in line or lowered.startswith(("git+", "hg+", "svn+", "bzr+")):
            return None, "Invalid requirement (URLs/VCS installs are not allowed)."

        if not _REQ_LINE_ALLOWED_RE.match(line):
            return None, "Invalid requirement (unsupported characters)."

        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(line)

    out.sort(key=str.lower)
    return out, None


def _merge_pip_requirements(existing: object, new: list[str]) -> list[str]:
    if not isinstance(existing, list):
        existing_list: list[str] = []
    else:
        existing_list = [x for x in existing if isinstance(x, str)]
    merged: list[str] = existing_list + new
    out: list[str] = []
    seen: set[str] = set()
    for line in merged:
        s = line.strip()
        if not s:
            continue
        k = s.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
    out.sort(key=str.lower)
    return out


@bp.post("/token")
def mint_terminal_ws_token():
    """Mint a short-lived, one-time token for the terminal WebSocket."""
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    ttl_seconds = int(current_app.config["TERMINAL_WS_TOKEN_TTL_SECONDS"])

    session["terminal_ws_token"] = token
    session["terminal_ws_token_exp"] = now + max(1, ttl_seconds)

    return jsonify({"token": token, "expiresInSeconds": max(1, ttl_seconds)})


@bp.get("/packages")
def get_terminal_packages():
    reqs = session.get(_SESSION_PIP_REQUIREMENTS_KEY) or []
    if not isinstance(reqs, list) or not all(isinstance(x, str) for x in reqs):
        reqs = []
        session.pop(_SESSION_PIP_REQUIREMENTS_KEY, None)
    return jsonify({"requirements": reqs})


@bp.post("/packages")
def set_terminal_packages():
    payload = request.get_json(silent=True) or {}
    normalized, err = _normalize_pip_requirements(payload)
    if err is not None:
        return jsonify({"error": err}), 400
    assert normalized is not None
    session[_SESSION_PIP_REQUIREMENTS_KEY] = normalized
    return jsonify({"requirements": normalized})


@bp.delete("/packages")
def clear_terminal_packages():
    session.pop(_SESSION_PIP_REQUIREMENTS_KEY, None)
    return jsonify({"requirements": []})


@bp.post("/pip-install")
def pip_install_into_session_sandbox():
    sandbox_id = session.get("e2b_terminal_sandbox_id") or ""
    if not isinstance(sandbox_id, str) or not sandbox_id.strip():
        return jsonify({"error": "No active E2B sandbox for this session."}), 400

    allow_internet = bool(current_app.config["E2B_ALLOW_INTERNET_ACCESS"])
    if not allow_internet:
        return (
            jsonify(
                {
                    "error": "pip installs require internet access. Set E2B_ALLOW_INTERNET_ACCESS=1."
                }
            ),
            400,
        )

    payload = request.get_json(silent=True) or {}
    normalized, err = _normalize_pip_requirements(payload)
    if err is not None:
        return jsonify({"error": err}), 400
    assert normalized is not None

    # Persist requested packages in this browser session (dedupe, stable order).
    session[_SESSION_PIP_REQUIREMENTS_KEY] = _merge_pip_requirements(
        session.get(_SESSION_PIP_REQUIREMENTS_KEY), normalized
    )

    try:
        from e2b import Sandbox  # type: ignore

        sandbox = Sandbox.connect(str(sandbox_id).strip())
    except Exception:
        session.pop("e2b_terminal_sandbox_id", None)
        return jsonify({"error": "Failed to connect to the session sandbox."}), 409

    req_path = "/tmp/interactive-docs-runtime-requirements.txt"
    try:
        sandbox.files.write(req_path, "\n".join(normalized) + "\n")
    except Exception:
        return jsonify({"error": "Failed to write requirements file in sandbox."}), 500

    timeout_seconds = int(current_app.config["TERMINAL_PIP_INSTALL_TIMEOUT_SECONDS"])
    try:
        result = sandbox.commands.run(
            f"python -m pip install --no-input --disable-pip-version-check -r {req_path}",
            timeout=timeout_seconds,
        )
    except Exception:
        return jsonify({"error": "pip install failed (exception)."}), 500

    return jsonify(
        {
            "exit_code": int(getattr(result, "exit_code", 0) or 0),
            "stdout": str(getattr(result, "stdout", "") or ""),
            "stderr": str(getattr(result, "stderr", "") or ""),
        }
    )


@bp.post("/kill")
def kill_terminal_sandbox():
    """Best-effort kill of the current browser session's E2B sandbox."""
    sandbox_id = session.pop("e2b_terminal_sandbox_id", None)
    if not sandbox_id:
        return jsonify({"killed": False})

    try:
        from e2b import Sandbox  # type: ignore

        killed = bool(Sandbox.kill(str(sandbox_id)))
        return jsonify({"killed": killed})
    except Exception:
        return jsonify({"killed": False})
