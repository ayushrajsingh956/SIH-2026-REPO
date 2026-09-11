import logging
from typing import Any

from app.services.notifications.interface import (
    NotificationEvent,
    NotificationSink,
    ScanFailedEvent,
    ScanNeedsReviewEvent,
)
from app.services.notifications.log_sink import LogSink

logger = logging.getLogger(__name__)


class NotificationService:
    """Central notification dispatcher for legal metrology enforcement events."""

    def __init__(self, sink: NotificationSink | None = None) -> None:
        self._sink: NotificationSink = sink or LogSink()

    def set_sink(self, sink: NotificationSink) -> None:
        self._sink = sink

    @property
    def sink(self) -> NotificationSink:
        return self._sink

    async def send(self, recipient: str, event: NotificationEvent) -> bool:
        try:
            return await self._sink.send(recipient=recipient, event=event)
        except Exception as exc:
            logger.error("Failed to send notification to '%s': %s", recipient, exc)
            return False

    async def notify_scan_needs_review(
        self,
        scan_id: str,
        recipient: str = "inspector-alerts@legalmetro.gov.in",
        reason: str = "Low extraction confidence or rule check exception",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        event = ScanNeedsReviewEvent(scan_id=scan_id, reason=reason, metadata=metadata)
        return await self.send(recipient, event)

    async def notify_scan_failed(
        self,
        scan_id: str,
        error_msg: str,
        recipient: str = "admin-alerts@legalmetro.gov.in",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        event = ScanFailedEvent(scan_id=scan_id, error_msg=error_msg, metadata=metadata)
        return await self.send(recipient, event)


_default_service: NotificationService | None = None


def get_notification_service() -> NotificationService:
    global _default_service
    if _default_service is None:
        _default_service = NotificationService()
    return _default_service
