# interactive documentation

Local web app: Flask backend, HTML templates (Jinja2), hand-written CSS under `app/static/css/`, and **React (JSX)** built with **Vite** into `app/static/dist/` for pages that opt in.

The home page includes a **chat bar** at the **bottom of the main (left) column** built with [**MUI X Chat**](https://mui.com/x/react-chat/) (`@mui/x-chat`) and **Material UI**. It talks to Flask **`POST /api/chat`**, which streams **newline-delimited JSON** chunks compatible with MUI X Chat’s stream processor.

**`@mui/x-chat` is alpha** on npm; APIs may change between releases. Pin or upgrade deliberately.

Requires **Python 3.9+** and **Node.js 18+**.

## Setup

### Python

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\activate`.

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
flask --app app:create_app run --debug
```

**Alternatives:**

```bash
python run.py
```

```bash
python -m app
```

Open [http://127.0.0.1:5000/](http://127.0.0.1:5000/).

## Chat API (stub)

- **`POST /api/chat`** — JSON body: `{ "conversationId": "...", "message": { "id", "role", "parts" } }`.
- Response: **`application/x-ndjson`** stream; each line is one JSON object (`start`, `text-delta`, `text-end`, `finish`, …) for MUI X Chat.
- Implementation: [`app/chat.py`](app/chat.py) (streaming stub; replace with a real model later).

## Frontend development

- **Rebuild on save + Flask:** in `frontend/`, run `npm run build:watch` in one terminal and Flask in another. Refresh the browser after each build.
- **Vite dev server:** `cd frontend && npm run dev` (e.g. [http://localhost:5173/](http://localhost:5173/)). **`vite.config.js`** proxies **`/api`** to **`http://127.0.0.1:5000`** — run Flask on port 5000 while using Vite for HMR. The Vite `index.html` only mounts React; for the full Jinja layout, use Flask.

## Layout

- `app/__init__.py` — application factory `create_app()`
- `app/routes.py` — routes (blueprint `main`)
- `app/chat.py` — `POST /api/chat` streaming stub (blueprint `chat`, prefix `/api`)
- `app/templates/` — Jinja; React mounts at `#react-root` in **`page__chat-bar`** (bottom of the left column only)
- `app/static/` — CSS and Vite output under `app/static/dist/`
- `frontend/` — Vite + React source, `npm run build` → `app/static/dist/`
