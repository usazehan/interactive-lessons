"""Outbound email.

Console backend by default: it logs the message (including any verification /
reset link) instead of sending it, so the auth flows work end-to-end without
SMTP. Swap `send_email` for a real provider (SMTP, SES, SendGrid, ...) without
touching the callers.
"""
import logging

logger = logging.getLogger("app.email")


def send_email(to: str, subject: str, body: str) -> None:
    # Replace this body with a real transport in production.
    logger.info("EMAIL to=%s | %s\n%s", to, subject, body)
    print(f"[email] to={to} | {subject}\n{body}")
