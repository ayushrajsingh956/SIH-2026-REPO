import logging

from app.services.notifications.interface import NotificationEvent, NotificationSink

logger = logging.getLogger("app.notifications")


class LogSink(NotificationSink):
    """Development and audit implementation that records notifications to application logs."""

    def __init__(self) -> None:
        self.sent_events: list[tuple[str, NotificationEvent]] = []

    async def send(self, recipient: str, event: NotificationEvent) -> bool:
        logger.info(
            "[NOTIFICATION DISPATCHED] [%s] Recipient: %s | Title: %s | Message: %s | Meta: %s",
            event.event_type.upper(),
            recipient,
            event.title,
            event.message,
            event.metadata,
        )
        self.sent_events.append((recipient, event))
        return True
