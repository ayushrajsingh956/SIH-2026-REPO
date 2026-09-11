import uuid

import pytest

from app.services.notifications import (
    LogSink,
    NotificationService,
    ScanFailedEvent,
    ScanNeedsReviewEvent,
    SMTPSink,
    get_notification_service,
)
from app.tasks.scan_pipeline import _async_mark_scan_failed


@pytest.mark.anyio
class TestNotificationsService:
    async def test_logsink_records_and_formats_events(self):
        sink = LogSink()
        service = NotificationService(sink=sink)

        scan_id = str(uuid.uuid4())
        res = await service.notify_scan_needs_review(
            scan_id=scan_id,
            reason="Confidence 0.42 below 0.6 threshold",
            metadata={"confidence": 0.42},
        )
        assert res is True
        assert len(sink.sent_events) == 1
        recipient, event = sink.sent_events[0]
        assert recipient == "inspector-alerts@legalmetro.gov.in"
        assert isinstance(event, ScanNeedsReviewEvent)
        assert event.scan_id == scan_id
        assert event.event_type == "scan.needs_review"
        assert "0.42" in event.message

    async def test_notify_scan_failed_event(self):
        sink = LogSink()
        service = NotificationService(sink=sink)

        scan_id = str(uuid.uuid4())
        res = await service.notify_scan_failed(
            scan_id=scan_id,
            error_msg="OpenCV decoding exception: corrupted JPEG stream",
        )
        assert res is True
        assert len(sink.sent_events) == 1
        recipient, event = sink.sent_events[0]
        assert recipient == "admin-alerts@legalmetro.gov.in"
        assert isinstance(event, ScanFailedEvent)
        assert event.scan_id == scan_id
        assert event.event_type == "scan.failed"
        assert "corrupted JPEG" in event.message

    async def test_smtp_sink_stub_dispatch(self):
        smtp = SMTPSink(smtp_host="mail.gov.in", smtp_port=587)
        service = NotificationService(sink=smtp)
        scan_id = str(uuid.uuid4())
        event = ScanFailedEvent(scan_id=scan_id, error_msg="Timeout connecting to vision model")
        success = await service.send(recipient="officer@nic.in", event=event)
        assert success is True

    async def test_mark_scan_failed_dispatches_notification(self, monkeypatch):
        test_sink = LogSink()
        svc = get_notification_service()
        orig_sink = svc.sink
        svc.set_sink(test_sink)

        try:
            fake_scan_id = str(uuid.uuid4())
            await _async_mark_scan_failed(fake_scan_id, "Test pipeline crash")
            assert len(test_sink.sent_events) >= 1
            recipient, event = test_sink.sent_events[-1]
            assert event.scan_id == fake_scan_id
            assert "Test pipeline crash" in event.message
        finally:
            svc.set_sink(orig_sink)
