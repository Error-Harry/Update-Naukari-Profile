# syntax=docker/dockerfile:1.6

# =====================================================================
# Server-only image (API + APScheduler + Playwright runner).
# Build context is `server/` — set Render's "Root Directory" to `server`
# so this Dockerfile becomes the build entry.
# =====================================================================

# The official Playwright Python image already has Chromium and every shared
# library it depends on (libnss3, libasound2, libcups2, fonts, …) installed,
# so we don't have to fight apt-get on a minimal base.
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

# xvfb gives headed Chromium a virtual display. Naukri blocks true headless.
RUN apt-get update \
    && apt-get install -y --no-install-recommends xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so they get cached across code-only changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the server code (`app/`, `naukari_bot/`, `scripts/`, …).
# See `.dockerignore` for what's stripped out.
COPY . .

# Render injects $PORT. Keep a sane default for local `docker run`.
ENV PORT=8000 \
    PLAYWRIGHT_HEADED=1 \
    BROWSER_CONCURRENCY=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Single uvicorn worker under xvfb. APScheduler lives in-process, so running
# multiple workers would schedule every cron N times — we explicitly cap at 1.
CMD xvfb-run -a --server-args="-screen 0 1920x1080x24" \
    uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
