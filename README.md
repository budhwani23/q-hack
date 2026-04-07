# React + FastAPI — Single-Image Starter

A minimal full-stack template: **React 18 + Vite** frontend, **FastAPI** backend, shipped as a **single Docker image** deployable to [Koyeb](https://koyeb.com) (or any container host).

```
react-fastapi-app/
├── frontend/           # React (Vite) — src, index.html, vite.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       └── App.css / index.css
├── backend/            # FastAPI
│   └── app/
│       ├── main.py     # mounts /api routes + serves React build
│       └── api/
│           └── routes.py
├── Dockerfile          # multi-stage: Node build → Python runtime
├── .dockerignore
└── .gitignore
```

---

## Local development

### Frontend (hot-reload)
```bash
cd frontend
npm install
npm run dev          # http://localhost:5173  (proxies /api → :8000)
```

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:5173` — the Vite dev server proxies `/api/*` to FastAPI.

---

## Build & run with Docker

```bash
# Build the single image
docker build -t react-fastapi-app .

# Run locally
docker run -p 8000:8000 react-fastapi-app

# Open http://localhost:8000
```

The React app is compiled in the first build stage and embedded into the Python image. FastAPI serves the static files at `/` and the API at `/api/*`.

---

## Deploy to Koyeb

1. **Push your image** to a registry (Docker Hub, GHCR, etc.):
   ```bash
   docker tag react-fastapi-app <your-registry>/react-fastapi-app:latest
   docker push <your-registry>/react-fastapi-app:latest
   ```

2. **Create a Koyeb service** — Web Service → Docker image.

3. **Set the port** to `8000` (or let Koyeb inject `$PORT` — the `CMD` already reads it).

4. That's it. No separate frontend service needed.

### Environment variables

| Variable       | Default | Description                          |
|----------------|---------|--------------------------------------|
| `PORT`         | `8000`  | Port Uvicorn listens on              |
| `CORS_ORIGINS` | `*`     | Comma-separated list of allowed origins |

---

## API endpoints

| Method | Path          | Description        |
|--------|---------------|--------------------|
| GET    | `/api/health` | Health check       |
| GET    | `/api/hello`  | Sample greeting    |
| GET    | `/api/docs`   | Swagger UI         |

Add your own routes in `backend/app/api/routes.py` and include them in `backend/app/main.py`.
