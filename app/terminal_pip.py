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


def maybe_install_pip_requirements_for_terminal_session(
    *,
    terminal_provider: str,
    sandbox_id: str | None,
    pip_requirements: object,
) -> tuple[list[str] | None, str | None, int | None]:
    """Optionally install pip requirements based on terminal provider.

    Returns (normalized_requirements, err, http_status).

    - For E2B providers, installs into the session sandbox (requires sandbox id).
    - For other providers, does nothing.
    """
    req_lines = _coerce_pip_requirements_lines(pip_requirements)

    if not any(isinstance(x, str) and x.strip() for x in req_lines):
        return None, None, None

    provider = str(terminal_provider or "").strip().lower()
    if provider not in ("e2b", "e2b-sandbox"):
        return None, None, None

    sid = str(sandbox_id or "").strip()
    if not sid:
        return None, None, None

    result, err, status = pip_install_requirements_into_session_sandbox(
        sandbox_id=sid,
        requirements=req_lines,
    )
    if err is not None:
        return None, err, status

    normalized = (result or {}).get("normalized_requirements", None)
    if isinstance(normalized, list) and all(isinstance(x, str) for x in normalized):
        return normalized, None, status

    return None, "pip install succeeded but returned invalid normalized requirements.", 500


def _coerce_pip_requirements_lines(pip_requirements: object) -> list[str]:
    if isinstance(pip_requirements, str):
        return [ln.strip() for ln in pip_requirements.splitlines()]
    if isinstance(pip_requirements, list):
        return list(pip_requirements)
    return []


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


# Future: automatically populate this mapping from the E2B CPU wheels.

CPU_MAPPING = {
    "torch": ["torch", "--extra-index-url", "https://download.pytorch.org/whl/cpu"],
    "torchvision": ["torchvision", "--extra-index-url", "https://download.pytorch.org/whl/cpu"],
    "tensorflow": ["tensorflow-cpu"],
    "jax": ["jax[cpu]"],
    "vllm": ["vllm", "--extra-index-url", "https://wheels.vllm.ai/nightly/cpu"],
    "xgboost": ["xgboost-cpu"],
}


def _normalize_pip_requirements(
    reqs: object,
    *,
    apply_e2b_cpu_mapping: bool = True,
) -> tuple[list[str] | None, str | None]:
    """Validate + normalize requirement lines for session-scoped pip installs.

    Intentionally conservative: accept simple package specs and version pins,
    but reject pip options, URLs/VCS installs, and multi-line / control chars.

    When ``apply_e2b_cpu_mapping`` is true, known heavy / GPU-first packages are
    rewritten via ``CPU_MAPPING`` for CPU wheels compatible with E2B sandboxes;
    ``--extra-index-url`` lines emitted from that mapping are allowed in the
    generated requirements file. Host-side (local) installs pass ``False`` so
    requirements stay as requested.
    """
    max_lines = int(current_app.config["TERMINAL_MAX_PIP_REQUIREMENTS_LINES"])
    max_chars = int(current_app.config["TERMINAL_MAX_PIP_REQUIREMENT_LINE_CHARS"])
    if reqs is None:
        return None, 'Missing "requirements".'
    if not isinstance(reqs, list):
        return None, '"requirements" must be a list of strings.'
    if max_lines > 0 and len(reqs) > max_lines:
        return None, f"Too many requirements (max {max_lines})."

    option_lines: list[str] = []
    package_lines: list[str] = []
    seen_option: set[str] = set()
    seen_package: set[str] = set()

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

        expanded = (
            _expand_e2b_cpu_requirement_line(line)
            if apply_e2b_cpu_mapping
            else [line]
        )
        for exp in expanded:
            err = _validate_expanded_requirement_line(exp, max_chars=max_chars)
            if err is not None:
                return None, err
            s = exp.strip()
            if s.startswith("--"):
                k = s.lower()
                if k in seen_option:
                    continue
                seen_option.add(k)
                option_lines.append(s)
            else:
                k = s.lower()
                if k in seen_package:
                    continue
                seen_package.add(k)
                package_lines.append(s)

    package_lines.sort(key=str.lower)
    out = option_lines + package_lines
    return out, None


def _expand_e2b_cpu_requirement_line(line: str) -> list[str]:
    m = _CPU_PKG_HEAD_RE.match(line.strip())
    if not m:
        return [line]
    name, _bracket, tail = m.group(1), m.group(2) or "", m.group(3) or ""
    key = name.lower()
    if key not in CPU_MAPPING:
        return [line]
    parts = CPU_MAPPING[key]
    out: list[str] = []
    i = 0
    if i < len(parts) and not str(parts[i]).strip().startswith("-"):
        out.append(str(parts[i]) + tail)
        i += 1
    while i < len(parts):
        p = str(parts[i])
        if (
            p == "--extra-index-url"
            and i + 1 < len(parts)
            and str(parts[i + 1]).startswith("https://")
        ):
            out.append(f"--extra-index-url {parts[i + 1]}")
            i += 2
        else:
            out.append(p)
            i += 1
    return out


def _validate_expanded_requirement_line(line: str, *, max_chars: int) -> str | None:
    if max_chars > 0 and len(line) > max_chars:
        return f"Requirement too long (max {max_chars} chars)."
    if any(ord(ch) < 32 for ch in line) or "\n" in line or "\r" in line:
        return "Invalid requirement (control characters)."
    s = line.strip()
    if s.startswith("--"):
        if not _EXTRA_INDEX_URL_LINE_RE.match(s):
            return "Invalid requirement (unsupported pip option)."
        return None
    if s.startswith("-"):
        return "Invalid requirement (pip options are not allowed)."
    lowered = s.lower()
    if " -r " in f" {lowered} ":
        return "Invalid requirement (recursive requirements not allowed)."
    if "://" in s or lowered.startswith(("git+", "hg+", "svn+", "bzr+")):
        return "Invalid requirement (URLs/VCS installs are not allowed)."
    if not _REQ_LINE_ALLOWED_RE.match(s):
        return "Invalid requirement (unsupported characters)."
    return None


_CPU_PKG_HEAD_RE = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9_.-]*)(\[[^\]]*])?(.*)$",
)
_EXTRA_INDEX_URL_LINE_RE = re.compile(r"^--extra-index-url https://\S+$")
