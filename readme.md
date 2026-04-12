# interactive documentation

Local web app: Flask backend, HTML templates (Jinja2), hand-written CSS under `app/static/css/`, and **React (JSX)** built with **Vite** into `app/static/dist/` for pages that opt in.

Requires **Python 3** and **Node.js 18+** (for `npm` / Vite).

## Setup

### Python

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\activate`.

### Frontend (React + Vite)

```bash
cd frontend
npm install
npm run build
```

The build writes `app/static/dist/assets/main.js` and `main.css`. Flask serves them as `/static/dist/assets/...`. Run `npm run build` whenever you change `frontend/src/` before loading the app via Flask (unless you use the Vite dev server; see below).

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

## Frontend development

- **Rebuild on save + Flask:** in `frontend/`, run `npm run build:watch` in one terminal and Flask in another. Refresh the browser after each build.
- **Vite dev server (fast HMR):** `cd frontend && npm run dev` — opens the Vite app (default [http://localhost:5173/](http://localhost:5173/)). Use this for UI work; use Flask when you need server-rendered templates or Python APIs. Add a `server.proxy` in `frontend/vite.config.js` later if you need to call Flask APIs from the Vite origin without CORS.

## Layout

- `app/__init__.py` — application factory `create_app()`
- `app/routes.py` — routes (blueprint `main`)
- `app/templates/` — HTML templates (Jinja); React mounts at `#react-root` in `base.html`
- `app/static/` — CSS, images, and Vite build output under `app/static/dist/`
- `frontend/` — Vite + React source (`src/`), `npm run build` → `app/static/dist/`
