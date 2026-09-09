"""Sending providers behind an interface.

V1 ships:
- NullOutreachProvider: safe dev default. Records intent, returns NOT_CONFIGURED.
  Never reports a fake successful send.
- SmtpEmailProvider: real SMTP send, active only when SMTP_* env vars are set.

WhatsApp has no send integration in V1 -> NOT_CONFIGURED.
"""

from __future__ import annotations

import abc
import os
from dataclasses import dataclass

from app.core.logging import get_logger
from app.db.models.enums import OutreachChannel, OutreachStatus

log = get_logger(__name__)


@dataclass
class SendResult:
    ok: bool
    status: OutreachStatus
    provider: str
    reference: str | None = None
    detail: str | None = None


class OutreachProvider(abc.ABC):
    name: str
    channel: OutreachChannel

    @abc.abstractmethod
    async def configured(self) -> bool: ...

    @abc.abstractmethod
    async def send(self, *, to: str | None, subject: str | None, body: str) -> SendResult: ...


class NullOutreachProvider(OutreachProvider):
    def __init__(self, channel: OutreachChannel) -> None:
        self.channel = channel
        self.name = f"null:{channel.value.lower()}"

    async def configured(self) -> bool:
        return False

    async def send(self, *, to: str | None, subject: str | None, body: str) -> SendResult:
        log.warning("outreach.send.not_configured", channel=self.channel.value, to=to)
        return SendResult(
            ok=False,
            status=OutreachStatus.NOT_CONFIGURED,
            provider=self.name,
            detail="No sending integration configured for this channel",
        )


class SmtpEmailProvider(OutreachProvider):
    name = "smtp"
    channel = OutreachChannel.EMAIL

    async def configured(self) -> bool:
        return all(os.environ.get(k) for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_FROM"))

    async def send(self, *, to: str | None, subject: str | None, body: str) -> SendResult:
        if not to:
            return SendResult(False, OutreachStatus.NOT_CONFIGURED, self.name,
                              detail="no recipient address")
        import asyncio
        import smtplib
        from email.message import EmailMessage

        def _send() -> str:
            msg = EmailMessage()
            msg["From"] = os.environ["SMTP_FROM"]
            msg["To"] = to
            msg["Subject"] = subject or "(no subject)"
            msg.set_content(body)
            host, port = os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"])
            with smtplib.SMTP(host, port, timeout=20) as srv:
                if os.environ.get("SMTP_STARTTLS", "true").lower() == "true":
                    srv.starttls()
                if os.environ.get("SMTP_USER"):
                    srv.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
                srv.send_message(msg)
            return msg.get("Message-ID") or "sent"

        try:
            ref = await asyncio.to_thread(_send)
            log.info("outreach.send.smtp.ok", to=to)
            return SendResult(True, OutreachStatus.SENT, self.name, reference=ref)
        except Exception as exc:  # noqa: BLE001
            log.error("outreach.send.smtp.failed", to=to, error=str(exc))
            return SendResult(False, OutreachStatus.NOT_CONFIGURED, self.name, detail=str(exc))


_email_override: OutreachProvider | None = None
_whatsapp_override: OutreachProvider | None = None


def set_provider(channel: OutreachChannel, provider: OutreachProvider | None) -> None:
    global _email_override, _whatsapp_override
    if channel == OutreachChannel.EMAIL:
        _email_override = provider
    else:
        _whatsapp_override = provider


async def get_outreach_provider(channel: OutreachChannel) -> OutreachProvider:
    override = _email_override if channel == OutreachChannel.EMAIL else _whatsapp_override
    if override is not None:
        return override
    if channel == OutreachChannel.EMAIL:
        smtp = SmtpEmailProvider()
        if await smtp.configured():
            return smtp
    return NullOutreachProvider(channel)
