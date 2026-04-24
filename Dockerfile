# syntax=docker/dockerfile:1.6

# =====================================================================
# Stage 1 — build the React / Vite frontend
# =====================================================================
FROM node:20-alpine AS frontend
WORKDIR /build/frontend

# Install deps with a reproducible lockfile when available.
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY frontend ./
RUN npm run build
# output: /build/frontend/dist


# =====================================================================
# Stage 2 — runtime image with Python, Chromium, Playwright, xvfb
# =====================================================================
# The official Playwright Python image already has Chromium + every shared
# lib (libnss3, libasound2, libcups2, fonts, …) installed. Saves us from
# apt-get hell on minimal bases.
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

# xvfb gives headed Chromium a virtual display — Naukri blocks true headless.
RUN apt-get update \
    && apt-get install -y --no-install-recommends xvfb \
    && rm -rf /var/lib/apt/lists/*

# Match the repo layout that server/app/main.py expects:
#   <repo_root>/server/...   (FastAPI code)
#   <repo_root>/frontend/dist (React build)
# main.py computes `_REPO_ROOT = ../..` from app/main.py, so the working
# directory at runtime must be /app/server.
WORKDIR /app

COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

COPY server ./server
COPY --from=frontend /build/frontend/dist ./frontend/dist

WORKDIR /app/server

# Render injects $PORT at runtime. Keep the default for local `docker run`.
ENV PORT=8000 \
    PLAYWRIGHT_HEADED=1 \
    BROWSER_CONCURRENCY=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Single-process uvicorn under xvfb. APScheduler lives in-process, so we run
# exactly one worker — more than one would schedule the same cron N times.
CMD xvfb-run -a --server-args="-screen 0 1920x1080x24" \
    uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
