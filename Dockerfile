# =============================================================================
# Stage 1 — Build the React frontend
# =============================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Install dependencies first (better layer caching)
# Use npm install so no pre-existing package-lock.json is required.
# Once you commit the generated package-lock.json you can switch this back to `npm ci`.
COPY frontend/package*.json ./
RUN npm install

# Copy source and build
COPY frontend/ ./
RUN npm run build

# =============================================================================
# Stage 2 — Python runtime + FastAPI + built frontend
# =============================================================================
FROM python:3.12-slim AS runtime

# Don't write .pyc files; unbuffered stdout/stderr for clean container logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./

# Copy the compiled React app into the location FastAPI will serve it from
COPY --from=frontend-builder /app/frontend/dist ./static

# Koyeb (and most platforms) injects $PORT; default to 8000 for local runs
ENV PORT=8000

# Expose the port (informational — Koyeb reads $PORT at runtime)
EXPOSE 8000

# Start the server
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
