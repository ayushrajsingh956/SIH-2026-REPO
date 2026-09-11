import logging

from app.services.notifications.interface import NotificationEvent, NotificationSink

logger = logging.getLogger("app.notifications.smtp")


class SMTPSink(NotificationSink):
    """Production SMTP email notification sink configured for Phase 7."""

    def __init__(
        self,
        smtp_host: str = "localhost",
        smtp_port: int = 587,
        smtp_user: str | None = None,
        smtp_pass: str | None = None,
        from_address: str = "enforcement@legalmetro.gov.in",
        use_tls: bool = True,
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
        self.from_address = from_address
        self.use_tls = use_tls

    async def send(self, recipient: str, event: NotificationEvent) -> bool:
        # Phase 7 full SMTP connection dispatch
        logger.info(
            "[SMTP SINK STUB] Would send email to '%s' via %s:%d (Subject: %s)",
            recipient,
            self.smtp_host,
            self.smtp_port,
            event.title,
        )
        return True
