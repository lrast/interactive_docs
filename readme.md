# Interactive Documentation

Quick demo app, providing access to documentation, a text editor, and terminal in one place, with an AI agent to tie them together.


## Overview

Local web app: Flask backend, HTML templates (Jinja2), CSS under `app/static/css/`, and React (JSX) built with Vite into `app/static/dist/`.

Pydantic AI provides a framework for for AI agents tool calling and output parsing, prompts under `app/prompts/`.

e2b provides cloud terminal instances.

Firecrawl fetches static versions or pages that are not iframe embeddable.




Requires **Python 3.10+** and **Node.js 18+**.

## Setup

### Python

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
npm run build
```

The build writes `app/static/dist/assets/main.js` and `main.css`. Flask serves them as `/static/dist/assets/...`. Run `npm run build` whenever you change `frontend/src/` before loading the app via Flask (unless you use the Vite dev server; see below).

### Environment

Flask reads configuration from the process environment. The following API keys should be set in a `.env` file or by `export`.
- **`SECRET_KEY`**: signing key for sessions and cookies. Defaults to a dev-only value; set explicitly in production.
- **`OPENAI_API_KEY`**: required for a agent calls (app/ai_calls.py). Pydantic-ai uses the provider’s usual credential environment variables, and can be modified to use an alternate model provider.
- **`FIRECRAWL_API_KEY`**: used for fetching documentation sites that are not iframe-embeddable.
- **`E2B_API_KEY`**: required to use e2b instances as remote terminals.
  * altenatively, ensure that **`TERMINAL_PROVIDER`** is set to `local` (default).

This application does not install pip requirements (or anything else) on local terminals, so requirements should be installed there as well.


## Run

### Recommended (Flask CLI, reload on Python/template changes):

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

### Hot reloading for frontend development

- **Rebuild on save + Flask:** in `frontend/`, run `npm run build:watch` in one terminal and Flask in another. Refresh the browser after each build.
- **Vite dev server:** `cd frontend && npm run dev` (e.g. [http://localhost:5173/](http://localhost:5173/)). **`vite.config.js`** proxies **`/api`** and **`/ws`** to **`http://127.0.0.1:5000`** — run Flask on port 5000 while using Vite for HMR. The Vite `index.html` only mounts React; for the full Jinja layout, use Flask.


### Open

[http://127.0.0.1:5000/](http://127.0.0.1:5000/).



## Key Settings

Optional and deployment-related environment variables are read in [`app/__init__.py`](app/__init__.py). **`SECRET_KEY`**, **`OPENAI_API_KEY`**, **`FIRECRAWL_API_KEY`**, and **`E2B_API_KEY`** are summarized under [Environment](#environment) above.

### Flask and sessions

- **`FLASK_SESSION_COOKIE_SECURE`**: `1` or `0` — set session cookies `Secure` when the site is served over HTTPS (default `0`).
- **`SESSION_LIFETIME_DAYS`**: signed session lifetime in days (default `31`).
- **`FLASK_SESSION_TYPE`**: Flask-Session backend type (default `filesystem`).
- **`FLASK_SESSION_FILE_DIR`**: directory for filesystem-backed sessions (defaults under the app instance path).

### Terminal provider and E2B

- **`TERMINAL_PROVIDER`**: `local` (default), `e2b`, or `disabled`. See [Terminal providers](#terminal-providers-local-vs-e2b).
- **`TERMINAL_ALLOW_REMOTE`**: `1` or `0` — relax localhost-only assumptions when you intend remote access (default `0`).
- **`E2B_TEMPLATE_NAME`**: E2B sandbox template id (default `interactive-docs-ipython`).
- **`E2B_ALLOW_INTERNET_ACCESS`**: `1` or `0` — allow outbound network from E2B sandboxes (default **`1`** in application code). Set **`0`** when dependencies are baked into the template and you want no runtime egress. Server-side pip installs into the live sandbox require **`1`**.

### Terminal WebSocket security

- **`TERMINAL_REQUIRE_TOKEN`**: `1` or `0` — require a minted token on `/ws/terminal` (defaults **`1`** for `e2b`, **`0`** for `local`).
- **`TERMINAL_ENFORCE_ORIGIN`**: `1` or `0` — validate `Origin` on the terminal WebSocket (default **`1`**).
- **`TERMINAL_WS_TOKEN_TTL_SECONDS`**: one-time token lifetime in seconds (default **`60`**).

### Terminal limits and pip install guards

- **`TERMINAL_MAX_SESSION_SECONDS`**: maximum WebSocket session length (default **`3600`**; **`0`** disables).
- **`TERMINAL_IDLE_TIMEOUT_SECONDS`**: idle disconnect for **E2B** sessions (default **`300`** seconds; **`0`** disables).
- **`TERMINAL_IDLE_TIMEOUT_SECONDS_LOCAL`**: idle disconnect for **local PTY** sessions only (default **`1200`**; **`0`** disables).
- **`TERMINAL_MAX_INBOUND_BYTES`**: maximum inbound WebSocket message size (default **`65536`**).
- **`TERMINAL_MAX_PIP_REQUIREMENTS_LINES`**: max lines accepted for a pip requirements batch (default **`50`**).
- **`TERMINAL_MAX_PIP_REQUIREMENT_LINE_CHARS`**: max characters per requirement line (default **`200`**).
- **`TERMINAL_PIP_INSTALL_TIMEOUT_SECONDS`**: timeout for server-side pip installs into an E2B sandbox (default **`600`**).

## Sidebar IPython terminal

- The lower-right sidebar runs **`ipython`** in the browser over **xterm.js**, a **`/ws/terminal`** WebSocket, and a PTY. **`ipython`** is listed in `requirements.txt`.
- **Unix only** (macOS / Linux). On Windows the socket responds with an unsupported message instead of spawning a PTY.
- **Security:** arbitrary code execution as the Flask OS user. Treat as **localhost-only, single-user** tooling; do not expose without isolation, authentication, and hardening.
- Code: [`app/terminal_session.py`](app/terminal_session.py), [`app/terminal_routes.py`](app/terminal_routes.py).

## Terminal providers (local vs E2B)

| Mode | Behavior |
|------|----------|
| **`TERMINAL_PROVIDER=local`** (default) | PTY + `ipython` on the same host as Flask. Intended for **local development**; access is guarded for localhost. |
| **`TERMINAL_PROVIDER=e2b`** | Terminal runs inside an **E2B** sandbox (better fit for deployment). Requires **`E2B_API_KEY`** and the **`e2b`** package from `requirements.txt`. |
| **`TERMINAL_PROVIDER=disabled`** | Terminal WebSocket is disabled. |

### E2B quick start

1. Install dependencies: `pip install -r requirements.txt` (includes **`e2b`**).
2. Set **`TERMINAL_PROVIDER=e2b`**, **`E2B_API_KEY`**, and optionally **`E2B_TEMPLATE_NAME`** (defaults and tuning: [Key Settings](#key-settings)).

### E2B IPython template (recommended)

Stock E2B images may not include `ipython`. Build a template that installs it so the REPL works **without** relying on runtime network access:

```bash
python e2b/build_template.py
```

Point **`E2B_TEMPLATE_NAME`** at that template (for example **`interactive-docs-ipython`**). After dependencies are baked in, you can run with **`E2B_ALLOW_INTERNET_ACCESS=0`** if you want no outbound network from sandboxes. Application default for that flag is **`1`** (see [Key Settings](#key-settings)).

### Pip installs in a live E2B session

When **`TERMINAL_PROVIDER=e2b`** and **`E2B_ALLOW_INTERNET_ACCESS=1`**, backend code can install packages into the **current** browser session’s sandbox via **`app.terminal_pip.pip_install_requirements_into_session_sandbox`** (requirements as a list of strings; on success you get `exit_code`, `stdout`, `stderr`, and `normalized_requirements`). There is no public HTTP route for ad-hoc installs—call this from your chat flow or another trusted server path.

### WebSocket security (production)

With token and origin checks enabled (defaults favor safety for **`e2b`**):

1. The client calls **`POST /api/terminal/token`** for a short-lived, one-time token.
2. The WebSocket connects to **`/ws/terminal?token=...`**.
3. The server rejects bad `Origin` headers and invalid or expired tokens.
4. **`POST /api/terminal/kill`** can stop the active sandbox (for example when the terminal UI unmounts); the client does not call it automatically on tab visibility changes.

Environment variables: [Key Settings → Terminal WebSocket security](#terminal-websocket-security).

### Idle clock and limits

While the tab is visible, the browser sends periodic **`{"type":"ping"}`** messages so the server can refresh idle timers and mitigate some proxy timeouts. Numeric limits are listed under [Key Settings → Terminal limits and pip install guards](#terminal-limits-and-pip-install-guards).

## Chat

The home chat bar sits at the **bottom of the main (left) column**. It uses [**MUI X Chat**](https://mui.com/x/react-chat/) (`@mui/x-chat`) and **Material UI**. **`@mui/x-chat` is alpha** on npm—pin or upgrade deliberately. It pulls in **`@mui/icons-material`** (declared in `frontend/package.json`).

- **`POST /api/chat`** — JSON body includes `conversationId`, `message` (`id`, `role`, `parts`), and optional editor and documentation URL fields the UI sends (see [`app/chat.py`](app/chat.py)).
- **Response:** **`application/x-ndjson`**; each line is one JSON object (`start`, `text-delta`, `text-end`, `ui-state`, `finish`, …) for MUI X Chat’s stream processor.
- **Model:** requests are handled with **Pydantic AI** in [`app/ai_calls.py`](app/ai_calls.py) (`OPENAI_API_KEY` and related provider env vars per [Environment](#environment)).

## Layout

- `app/__init__.py` — `create_app()`
- `app/routes.py` — blueprint `main`
- `app/chat.py` — blueprint `chat`, prefix `/api`; **`POST /api/chat`** streaming NDJSON
- `app/ai_calls.py` — Pydantic AI agent and tools for chat
- `app/terminal_routes.py` — HTTP routes plus WebSocket **`/ws/terminal`** (flask-sock)
- `app/templates/` — Jinja; React mounts at `#main-chat-root` in **`page__chat-bar`**
- `app/static/` — CSS and Vite output under `app/static/dist/`
- `frontend/` — Vite + React source; `npm run build` writes `app/static/dist/`
