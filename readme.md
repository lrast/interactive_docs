# Interactive Documentation

Quick app, providing access to documentation, a text editor, and terminal in one place, with an AI agent to tie them together.


## Overview

Local web app: Flask backend, HTML templates (Jinja2), CSS under `app/static/css/`, and **React (JSX)** built with **Vite** into `app/static/dist/` for pages that opt in.

The home page includes a **chat bar** at the **bottom of the main (left) column** built with [**MUI X Chat**](https://mui.com/x/react-chat/) (`@mui/x-chat`) and **Material UI**. It talks to Flask **`POST /api/chat`**, which streams **newline-delimited JSON** chunks compatible with MUI X Chat’s stream processor.

**`@mui/x-chat` is alpha** on npm; APIs may change between releases. Pin or upgrade deliberately.

Requires **Python 3.10+** and **Node.js 18+**.

## Setup

### Python

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\activate`.

**`FIRECRAWL_API_KEY`**: required when the model returns a documentation URL that is not iframe-embeddable (otherwise `POST /api/chat` fails while resolving the doc pane). Loaded from the environment into `app.config["FIRECRAWL_API_KEY"]` in `create_app`.

### Frontend (React + Vite + MUI X Chat)

```bash
cd frontend
npm install
npm run build
```

The build writes `app/static/dist/assets/main.js` and `main.css`. Flask serves them as `/static/dist/assets/...`. Run `npm run build` whenever you change `frontend/src/` before loading the app via Flask (unless you use the Vite dev server; see below).

`@mui/x-chat` depends on **`@mui/icons-material`** for some UI affordances; it is listed in `frontend/package.json` so Vite can bundle it.

## Run Flask

**Recommended (Flask CLI, reload on Python/template changes):**

```bash
flask --app app:create_app run --debug --host 127.0.0.1
```

Use **`--host 127.0.0.1`** (not `0.0.0.0`) so the sidebar **IPython terminal** (WebSocket + PTY) is not exposed on your LAN. The terminal runs shell code as the same OS user as Flask.

**Alternatives:**

```bash
python run.py
```

```bash
python -m app
```

Open [http://127.0.0.1:5000/](http://127.0.0.1:5000/).

## Sidebar IPython terminal (dev)

- The lower right sidebar runs a real **`ipython`** session in the browser (**xterm.js** + **`/ws/terminal`** WebSocket + PTY). Requires **`ipython`** from `requirements.txt` (installed with the venv).
- **Unix only** (macOS / Linux). On Windows the WebSocket responds with an unsupported message instead of spawning a PTY.
- **Security:** this is **arbitrary code execution** as your Flask OS user. Treat it as **localhost-only, single-user tooling**. Do not expose it on the public internet without strong isolation, auth, and hardening.
- Implementation: [`app/terminal_session.py`](app/terminal_session.py), [`app/terminal_routes.py`](app/terminal_routes.py).

## Terminal providers (local vs E2B)

The app supports multiple terminal execution providers controlled by env vars.

- **`TERMINAL_PROVIDER=local`** (default): local PTY + `ipython` on the same machine as Flask (**dev-only**; localhost guarded).
- **`TERMINAL_PROVIDER=e2b`**: run the terminal inside an **E2B sandbox** (safer for deployment).
- **`TERMINAL_PROVIDER=disabled`**: disables the terminal WebSocket.

### E2B setup

- Install deps:

```bash
pip install -r requirements.txt
```

- Set env:
  - **`E2B_API_KEY`**: required by the E2B SDK
  - **`TERMINAL_PROVIDER=e2b`**
  - **`E2B_TEMPLATE_NAME=interactive-docs-ipython`** (recommended; see below)

### E2B IPython template (recommended)

The default E2B base sandbox may not include `ipython`. To ensure the terminal starts an IPython REPL **without enabling outbound network at runtime**, build a custom E2B template that bakes `ipython` in.

- Build the template:

```bash
python e2b/build_template.py
```

- Then run the app with:
  - **`E2B_TEMPLATE_NAME=interactive-docs-ipython`**
  - **`E2B_ALLOW_INTERNET_ACCESS=0`** (default)

### Install packages during a live E2B session

When `TERMINAL_PROVIDER=e2b` and **`E2B_ALLOW_INTERNET_ACCESS=1`**, server code can install pip packages into the
current browser session's sandbox using **`app.terminal_pip.pip_install_requirements_into_session_sandbox`**
(requirements as a list of strings; returns `exit_code`, `stdout`, `stderr`, and `normalized_requirements` on success).

There is no public HTTP endpoint for ad-hoc pip installs; wire installs through your chat or other backend flow.

### WebSocket security (recommended for deploy)

When token/origin enforcement is enabled (defaults are secure for `e2b`):

- The frontend calls **`POST /api/terminal/token`** to mint a short-lived one-time token.
- The frontend calls **`POST /api/terminal/kill`** on page hide / background to best-effort stop the session E2B sandbox.
- The terminal WebSocket must connect to **`/ws/terminal?token=...`**.
- The server rejects mismatched `Origin` and invalid/expired tokens.

Config env vars:

- **`TERMINAL_REQUIRE_TOKEN`**: `1|0` (defaults to `1` for `e2b`, `0` for `local`)
- **`TERMINAL_ENFORCE_ORIGIN`**: `1|0` (default `1`)
- **`TERMINAL_WS_TOKEN_TTL_SECONDS`**: token TTL (default `60`)

### Limits / abuse controls

- **`TERMINAL_MAX_SESSION_SECONDS`**: max WS session duration (default `3600`, set `0` to disable)
- **`TERMINAL_IDLE_TIMEOUT_SECONDS`**: idle timeout (default `300`, set `0` to disable)
- **`TERMINAL_MAX_INBOUND_BYTES`**: per-message size limit (default `65536`)

## Chat API (stub)

- **`POST /api/chat`** — JSON body: `{ "conversationId": "...", "message": { "id", "role", "parts" } }`.
- Response: **`application/x-ndjson`** stream; each line is one JSON object (`start`, `text-delta`, `text-end`, `finish`, …) for MUI X Chat.
- Implementation: [`app/chat.py`](app/chat.py) (streaming stub; replace with a real model later).

## Frontend development

- **Rebuild on save + Flask:** in `frontend/`, run `npm run build:watch` in one terminal and Flask in another. Refresh the browser after each build.
- **Vite dev server:** `cd frontend && npm run dev` (e.g. [http://localhost:5173/](http://localhost:5173/)). **`vite.config.js`** proxies **`/api`** and **`/ws`** to **`http://127.0.0.1:5000`** — run Flask on port 5000 while using Vite for HMR. The Vite `index.html` only mounts React; for the full Jinja layout, use Flask.

## Layout

- `app/__init__.py` — application factory `create_app()`
- `app/routes.py` — routes (blueprint `main`)
- `app/chat.py` — `POST /api/chat` streaming stub (blueprint `chat`, prefix `/api`)
- `app/terminal_routes.py` — HTTP routes + WebSocket **`/ws/terminal`** (flask-sock) for the sidebar IPython PTY
- `app/templates/` — Jinja; React mounts at `#main-chat-root` in **`page__chat-bar`** (bottom of the left column only)
- `app/static/` — CSS and Vite output under `app/static/dist/`
- `frontend/` — Vite + React source, `npm run build` → `app/static/dist/`
