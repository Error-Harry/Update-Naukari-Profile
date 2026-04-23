"""Transactional emails (SMTP) sent from the service account."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from app.config import get_settings

log = logging.getLogger(__name__)


def send_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    attachment_bytes: Optional[bytes] = None,
    attachment_name: Optional[str] = None,
) -> None:
    s = get_settings()
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = s.smtp_email
        msg["To"] = to_email
        msg.set_content(body)
        if attachment_bytes and attachment_name:
            msg.add_attachment(
                attachment_bytes,
                maintype="application",
                subtype="pdf",
                filename=attachment_name,
            )
        with smtplib.SMTP(s.smtp_server, s.smtp_port) as smtp:
            smtp.starttls()
            smtp.login(s.smtp_email, s.smtp_password)
            smtp.send_message(msg)
        log.info("Email sent: %r to %s", subject, to_email)
    except Exception as e:  # noqa: BLE001
        log.error("Email failed (%s): %s", to_email, e)
