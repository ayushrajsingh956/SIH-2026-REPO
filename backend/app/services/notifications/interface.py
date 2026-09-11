from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol


@dataclass
class NotificationEvent:
    event_type: str
    scan_id: str
    title: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ScanNeedsReviewEvent(NotificationEvent):
    def __init__(self, scan_id: str, reason: str, metadata: dict[str, Any] | None = None):
        super().__init__(
            event_type="scan.needs_review",
            scan_id=scan_id,
            title="Scan Scrutiny Required",
            message=f"Scan {scan_id[:8]} flagged for officer review: {reason}",
            metadata=metadata or {"reason": reason},
        )


@dataclass
class ScanFailedEvent(NotificationEvent):
    def __init__(self, scan_id: str, error_msg: str, metadata: dict[str, Any] | None = None):
        super().__init__(
            event_type="scan.failed",
            scan_id=scan_id,
            title="Scan Processing Pipeline Failed",
            message=f"Scan {scan_id[:8]} processing failed: {error_msg}",
            metadata=metadata or {"error": error_msg},
        )


class NotificationSink(Protocol):
    """Protocol for dispatching statutory notification events."""

    async def send(self, recipient: str, event: NotificationEvent) -> bool:
        """Dispatches event to target recipient. Returns True if successfully handled."""
        ...
