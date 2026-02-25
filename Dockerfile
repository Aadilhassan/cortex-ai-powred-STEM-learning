# ============================================
# Cortex — All-in-one Docker image
# Backend (FastAPI) + Frontend (Astro) + Nginx
# ============================================

# --- Stage 1: Build frontend ---
FROM node:22-slim AS frontend-build

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# --- Stage 2: Runtime ---
FROM python:3.12-slim

# Install Node.js 22, Nginx, Supervisor
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl gnupg nginx supervisor && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install uv (Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# --- Backend setup ---
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/app/ app/
RUN mkdir -p data

# --- Frontend setup ---
WORKDIR /app/frontend
COPY --from=frontend-build /app/dist ./dist
COPY --from=frontend-build /app/node_modules ./node_modules

# --- Nginx config ---
RUN rm -f /etc/nginx/sites-enabled/default
COPY nginx/nginx-standalone.conf /etc/nginx/conf.d/cortex.conf

# --- Supervisor config ---
COPY supervisord.conf /etc/supervisor/conf.d/cortex.conf

# Data volume for SQLite DB
VOLUME /app/backend/data

EXPOSE 3000

CMD ["supervisord", "-n", "-c", "/etc/supervisor/conf.d/cortex.conf"]
