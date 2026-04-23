# Naukri Auto Update (SaaS edition)

Multi-user web app that keeps Naukri profiles fresh by re-uploading a resume and
bumping the resume headline on a daily schedule — so recruiters see your profile
at the top of their searches.

Each user signs up, stores their Naukri login + resume PDF, and picks when to run
(once or twice a day). A single Playwright runner on the server performs the
update for every user in sequence.

## Stack

- **API**: FastAPI (async) + SQLAlchemy 2 + asyncpg
- **DB**: Postgres (Neon tested)
- **Auth**: JWT (bcrypt for user passwords) + role-based access (`user` / `admin`)
- **At-rest encryption**: Fernet for each user's Naukri password
- **Scheduler**: APScheduler (AsyncIO) — one cron job per schedule slot, per user
- **Browser**: Playwright Chromium (run under `xvfb-run` on servers without a display)
- **Frontend**: React 18 + Vite + TypeScript + Tailwind + Radix UI + framer-motion + TanStack Query (in `frontend/`)
- **Billing**: mock `/api/me/billing` endpoints — drop in Stripe/Razorpay when ready

## Layout

```
server/                      Python backend (FastAPI + Playwright bot)
  requirements.txt
  app/                       FastAPI app + scheduler + UI
    main.py                  app entry (uvicorn runs this)
    config.py                env-driven settings
    db.py                    async engine / session
    models.py                SQLAlchemy ORM (users, naukri_profiles, run_logs)
    schemas.py               Pydantic request/response models
    security.py              bcrypt + JWT + Fernet
    deps.py                  FastAPI deps (current user, require_admin)
    emailer.py               SMTP helper
    scheduler.py             APScheduler wiring
    runner_service.py        executes a single user's Naukri update
    routers/
      auth.py                /api/auth/register, /api/auth/login
      users.py               /api/me (+ profile, resume, runs, run-now)
      billing.py             /api/me/billing (plan, subscribe, cancel)
      admin.py               /api/admin (users, runs, stats — admin only)
    static/                  legacy vanilla UI (fallback when the React build isn't built)
  naukari_bot/
    runner.py                reusable Playwright runner (RunConfig → RunResult)
    main.py                  legacy single-user CLI (uses the same runner)
    .env                     local single-user / SaaS .env (gitignored)
  scripts/
    run_naukari.sh           wrapper used by cron for the legacy CLI

frontend/                    React app (Vite + Tailwind + Radix)
  src/pages/                 Auth / Dashboard / Billing / Admin
  src/components/ui/         shadcn-style primitives (Button, Card, Switch, Dialog, …)
```

## Environment

Copy `.env.example` to `.env` and fill in the values. All keys are validated at
startup.

Generate a Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Local run

### Backend

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install --with-deps chromium
uvicorn app.main:app --reload
```

### Frontend (React dev server)

In another terminal, from the repo root:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** — Vite proxies `/api/*` to the FastAPI backend
running on `:8000`. Sign up, fill in Naukri profile, upload resume, pick a
schedule, save. Use "Run now" to test on demand.

### One-server build (production-style)

```bash
cd frontend && npm install && npm run build && cd ..
cd server && uvicorn app.main:app
```

Now FastAPI serves the built React app at **http://localhost:8000/** (and still
exposes the API under `/api`). If `frontend/dist` doesn't exist, the server
falls back to the old vanilla UI in `server/app/static/`.

### Becoming admin

Set `ADMIN_EMAIL=you@example.com` in `.env`. On every startup, that user is
promoted to the `admin` role — the **Admin** tab appears in the nav and you can
manage every user, toggle their subscription, or delete them.

## Production run (EC2 Ubuntu)

```bash
sudo apt-get install -y python3.12-venv xvfb nodejs npm

# build the React UI (outputs to frontend/dist, which FastAPI serves)
cd frontend && npm install && npm run build && cd ..

# backend
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install --with-deps chromium

# run the web app (behind nginx for TLS in prod)
PLAYWRIGHT_HEADED=1 xvfb-run -a --server-args="-screen 0 1920x1080x24" \
  uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Prefer a systemd unit in real deployments (see below).

### systemd unit (example)

Save as `/etc/systemd/system/naukri-app.service`:

```ini
[Unit]
Description=Naukri Auto Update (FastAPI + APScheduler)
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/update_resume/server
EnvironmentFile=/home/ubuntu/update_resume/server/naukari_bot/.env
ExecStart=/usr/bin/xvfb-run -a --server-args=-screen 0 1920x1080x24 \
  /home/ubuntu/update_resume/server/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now naukri-app
journalctl -u naukri-app -f
```

Put nginx (or Caddy) in front for TLS on port 443.

## Schedule semantics

- Each user has a `schedule_mode` of `once` or `twice` and 1–2 time-of-day slots.
- On profile save, APScheduler jobs are (re)created for that user.
- At startup the scheduler reloads every enabled profile's jobs from the DB.
- Server runs in the timezone set in `app/config.py` (`Asia/Kolkata` by default).

## Security

- User passwords: bcrypt hashes.
- Naukri passwords: Fernet-encrypted in Postgres (`naukri_profiles.naukri_password_enc`).
- Resume PDFs: stored as `bytea` in Postgres, served only to the owner.
- JWT for API auth; no refresh token flow (short/long tokens per `jwt_expire_minutes`).

## Notes

- Running Playwright on AWS/datacenter IPs can trigger Naukri's OTP step-up. Host
  the app where logins already succeed reliably (home IP or a long-lived EC2 with
  a steady session).
- The runner reuses a per-user Playwright profile directory under
  `var/pw-profiles/<user_id>/` to preserve cookies across runs.

## Legacy single-user CLI

`naukari_bot/main.py` still works for the env-driven single-user cron setup — it
now delegates to `naukari_bot/runner.py` so there's no duplicated logic.
