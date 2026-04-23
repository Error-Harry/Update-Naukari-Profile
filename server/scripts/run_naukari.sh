#!/usr/bin/env bash
# Wrapper used by cron to run the Naukri update bot.
# - Loads .env from naukari_bot/.env
# - Uses the project venv's Python directly (no activation needed)
# - Writes a per-day log under logs/
# - Exits non-zero on failure so cron/MAILTO can surface errors

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(dirname "${SCRIPT_DIR}")"
REPO_ROOT="$(dirname "${SERVER_DIR}")"

# venv lookup order: repo-root/.venv -> server/.venv
if [ -x "${REPO_ROOT}/.venv/bin/python" ]; then
    VENV_PYTHON="${REPO_ROOT}/.venv/bin/python"
elif [ -x "${SERVER_DIR}/.venv/bin/python" ]; then
    VENV_PYTHON="${SERVER_DIR}/.venv/bin/python"
else
    echo "No .venv found under ${REPO_ROOT} or ${SERVER_DIR}" >&2
    exit 127
fi

LOG_DIR="${SERVER_DIR}/logs"
TODAY="$(date +%Y-%m-%d)"
LOG_FILE="${LOG_DIR}/naukari_${TODAY}.log"

# Cron has no DISPLAY. Reuse the logged-in desktop session (local) OR let xvfb-run
# provide one (server). We fall back to xvfb-run if $DISPLAY isn't available.
export DISPLAY="${DISPLAY:-:0}"
if [ -z "${XAUTHORITY:-}" ] && [ -f "${HOME}/.Xauthority" ]; then
    export XAUTHORITY="${HOME}/.Xauthority"
fi

mkdir -p "${LOG_DIR}"
cd "${SERVER_DIR}"

{
    echo "=============================================="
    echo "Run started: $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "=============================================="
    "${VENV_PYTHON}" naukari_bot/main.py
    status=$?
    echo "=============================================="
    echo "Run finished with exit=$status at $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "=============================================="
    exit "$status"
} >> "${LOG_FILE}" 2>&1
