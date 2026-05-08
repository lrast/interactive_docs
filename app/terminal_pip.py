from __future__ import annotations

import re

from flask import current_app

_SESSION_PIP_REQUIREMENTS_KEY = "terminal_pip_requirements"
_REQ_LINE_ALLOWED_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-\[\],=<>!~+* ]*$")


def merge_pip_requirements(existing: object, new: list[str]) -> list[str]:
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


def pip_install_requirements_into_session_sandbox(
    *,
    sandbox_id: str,
    requirements: object,
    timeout_seconds: int | None = None,
) -> tuple[dict[str, object] | None, str | None, int]:
    """Install pip requirements into an E2B sandbox and return (result, err, http_status)."""
    if not isinstance(sandbox_id, str) or not sandbox_id.strip():
        return None, "No active E2B sandbox for this session.", 400

    allow_internet = bool(current_app.config["E2B_ALLOW_INTERNET_ACCESS"])
    if not allow_internet:
        return (
            None,
            "pip installs require internet access. Set E2B_ALLOW_INTERNET_ACCESS=1.",
            400,
        )

    normalized, err = _normalize_pip_requirements(requirements)
    if err is not None:
        return None, err, 400
    assert normalized is not None
    if not normalized:
        return None, 'Missing "requirements".', 400

    try:
        from e2b import Sandbox  # type: ignore

        sandbox = Sandbox.connect(str(sandbox_id).strip())
    except Exception:
        return None, "Failed to connect to the session sandbox.", 409

    req_path = "/tmp/interactive-docs-runtime-requirements.txt"
    try:
        sandbox.files.write(req_path, "\n".join(normalized) + "\n")
    except Exception:
        return None, "Failed to write requirements file in sandbox.", 500

    if timeout_seconds is None:
        timeout_seconds = int(current_app.config["TERMINAL_PIP_INSTALL_TIMEOUT_SECONDS"])

    try:
        #result = sandbox.commands.run("pip install cowsay")
        #result = sandbox.commands.run("pip install torch --no-cache-dir")

        result = sandbox.commands.run(
            f"pip install -r {req_path} --no-cache-dir",
            timeout=int(timeout_seconds),
        )
    except Exception as e:
        exit_code = getattr(e, "exit_code", None)
        stdout = str(getattr(e, "stdout", "") or "")
        stderr = str(getattr(e, "stderr", "") or "")
        stdout_tail = (stdout[-2000:] if len(stdout) > 2000 else stdout).strip()
        stderr_tail = (stderr[-2000:] if len(stderr) > 2000 else stderr).strip()

        pieces: list[str] = [f"{type(e).__name__}"]
        if isinstance(exit_code, int):
            pieces.append(f"exit_code={exit_code}")
        if stderr_tail:
            pieces.append(f"stderr_tail={stderr_tail}")
        elif stdout_tail:
            pieces.append(f"stdout_tail={stdout_tail}")

        return None, "pip install failed (" + ", ".join(pieces) + ")", 500

    return (
        {
            "exit_code": int(getattr(result, "exit_code", 0) or 0),
            "stdout": str(getattr(result, "stdout", "") or ""),
            "stderr": str(getattr(result, "stderr", "") or ""),
            "normalized_requirements": normalized,
        },
        None,
        200,
    )


def _normalize_pip_requirements(reqs: object) -> tuple[list[str] | None, str | None]:
    """Validate + normalize requirement lines for session-scoped pip installs.

    Intentionally conservative: accept simple package specs and version pins,
    but reject pip options, URLs/VCS installs, and multi-line / control chars.
    """
    max_lines = int(current_app.config["TERMINAL_MAX_PIP_REQUIREMENTS_LINES"])
    max_chars = int(current_app.config["TERMINAL_MAX_PIP_REQUIREMENT_LINE_CHARS"])
    if reqs is None:
        return None, 'Missing "requirements".'
    if not isinstance(reqs, list):
        return None, '"requirements" must be a list of strings.'
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
