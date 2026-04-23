"""
Thin CLI wrapper around `naukari_bot.runner.run_naukri_update`.

Reads credentials/SMTP config from environment (supports .env via python-dotenv)
so that the existing `cron` setup on EC2 keeps working exactly as before.
"""

from __future__ import annotations

import asyncio
import logging
import os
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage
from typing import Optional

# Allow `python naukari_bot/main.py` (direct script invocation) to resolve the
# `naukari_bot` package by putting the package's parent directory on sys.path.
_PKG_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PKG_PARENT not in sys.path:
    sys.path.insert(0, _PKG_PARENT)

from dotenv import load_dotenv

from naukari_bot.runner import RunConfig, run_naukri_update

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("naukari_bot.main")

EMAIL = os.getenv("EMAIL", "")
PASSWORD = os.getenv("PASSWORD", "")
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_SERVER = os.getenv("SMTP_SERVER", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
TO_EMAIL = os.getenv("TO_EMAIL", "")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_RESUME = os.path.join(_SCRIPT_DIR, "Harsh_Nargide.pdf")
_DEFAULT_USER_DATA_DIR = os.path.join(_SCRIPT_DIR, ".pw-profile")


def _validate_env() -> None:
    missing = [
        name for name, value in [
            ("EMAIL", EMAIL),
            ("PASSWORD", PASSWORD),
            ("SMTP_EMAIL", SMTP_EMAIL),
            ("SMTP_PASSWORD", SMTP_PASSWORD),
            ("SMTP_SERVER", SMTP_SERVER),
            ("TO_EMAIL", TO_EMAIL),
        ] if not value
    ]
    if missing:
        log.error("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(2)


def _resolve_user_data_dir() -> Optional[str]:
    explicit = os.getenv("NAUKRI_USER_DATA_DIR", "").strip()
    if explicit:
        return os.path.abspath(os.path.expanduser(explicit))
    if os.getenv("CI", "false").lower() == "true":
        return None
    return _DEFAULT_USER_DATA_DIR


def _send_email(subject: str, body: str, attachment_bytes: Optional[bytes] = None,
                attachment_name: Optional[str] = None) -> None:
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SMTP_EMAIL
        msg["To"] = TO_EMAIL
        msg.set_content(body)
        if attachment_bytes and attachment_name:
            msg.add_attachment(
                attachment_bytes,
                maintype="application",
                subtype="pdf",
                filename=attachment_name,
            )
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(SMTP_EMAIL, SMTP_PASSWORD)
            smtp.send_message(msg)
        log.info("Email sent successfully: '%s'", subject)
    except Exception as e:  # noqa: BLE001
        log.error("Email failed: %s", e)


async def _main() -> int:
    _validate_env()

    if not os.path.exists(BASE_RESUME):
        log.error("Resume file not found at %s", BASE_RESUME)
        return 2

    with open(BASE_RESUME, "rb") as f:
        resume_bytes = f.read()

    today = datetime.now().strftime("%d-%b-%Y")
    dated_name = f"Harsh_Nargide_{datetime.now().strftime('%d_%b_%Y')}.pdf"

    headed = os.getenv("PLAYWRIGHT_HEADED", "").lower() in ("1", "true", "yes")
    is_ci = os.getenv("CI", "false").lower() == "true"

    cfg = RunConfig(
        naukri_email=EMAIL,
        naukri_password=PASSWORD,
        resume_bytes=resume_bytes,
        resume_filename=dated_name,
        user_data_dir=_resolve_user_data_dir(),
        headed=headed or not is_ci,
    )

    result = await run_naukri_update(cfg)

    if result.success:
        _send_email(
            f"Resume & Profile Updated - {today}",
            f"Your resume and profile were successfully updated on {today}.",
            attachment_bytes=resume_bytes,
            attachment_name=dated_name,
        )
        return 0

    _send_email(
        f"Update Failed - {today}",
        f"Resume/Profile update failed after {cfg.max_retries} attempts.\n\nError: {result.error}",
    )
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
