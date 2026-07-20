from datetime import datetime, timezone
from uuid import uuid4

from app.extensions import db
from app.models import NotificationDelivery, NotificationOutbox
from scripts import notification_worker


def _pending_outbox():
    return NotificationOutbox(
        event_type="smtp_test",
        idempotency_key=f"test:{uuid4().hex}",
        recipient="shared-test@example.test",
        payload={"message": "worker test"},
        status="pending",
        next_attempt_at=datetime.now(timezone.utc),
    )


def test_worker_watch_delivers_each_outbox_row_once(app, monkeypatch):
    sent_ids = []
    monkeypatch.setattr(
        notification_worker,
        "_send",
        lambda _app, row: sent_ids.append(row.id) or f"mock-{row.id}",
    )
    with app.app_context():
        row = _pending_outbox()
        db.session.add(row)
        db.session.commit()
        row_id = row.id

    attempted, delivered = notification_worker.run_watch(
        app,
        interval_seconds=1,
        max_cycles=1,
        sleep=lambda _seconds: None,
    )
    assert (attempted, delivered) == (1, 1)
    assert sent_ids == [row_id]

    with app.app_context():
        row = db.session.get(NotificationOutbox, row_id)
        assert row.status == "sent"
        assert row.attempts == 1
        assert NotificationDelivery.query.filter_by(outbox_id=row_id, success=True).count() == 1
        assert notification_worker.run_batch(app) == (0, 0)


def test_email_content_is_continuous_readable_text():
    row = NotificationOutbox(
        event_type="waitlist_available",
        idempotency_key="email-copy-test",
        recipient="shared-test@example.test",
        payload={
            "institution": "澄心健康管理中心",
            "branch": "徐汇综合院区",
            "appointment_date": "2026-07-28",
            "party_size": 3,
            "message": "raw payload text",
        },
    )

    subject, body = notification_worker._email_content(row)

    assert subject == "HealthDoc 空位提醒"
    assert "澄心健康管理中心·徐汇综合院区" in body
    assert "2026年7月28日" in body
    assert "3位受检者" in body
    assert "不代表预约已经成功" in body
    assert "{\"" not in body and '"institution"' not in body
    assert body.endswith("本邮件由康康健健 HealthDoc 自动发送，请勿直接回复。")


def test_email_content_covers_institution_booking_events():
    booking = NotificationOutbox(
        event_type="booking_group_created",
        idempotency_key="booking-copy-test",
        recipient="shared-test@example.test",
        payload={
            "group_code": "BG-DEMO-001",
            "institution": "衡康代谢与慢病管理中心",
            "appointment_date": "2026-08-03",
            "package": "糖脂代谢专项",
            "party_size": 2,
        },
    )
    full = NotificationOutbox(
        event_type="appointment_date_full",
        idempotency_key="full-copy-test",
        recipient="shared-test@example.test",
        payload={
            "institution": "衡康代谢与慢病管理中心",
            "appointment_date": "2026-08-03",
        },
    )

    booking_subject, booking_body = notification_worker._email_content(booking)
    full_subject, full_body = notification_worker._email_content(full)

    assert booking_subject == "HealthDoc 新预约提醒"
    assert "BG-DEMO-001" in booking_body and "糖脂代谢专项" in booking_body
    assert full_subject == "HealthDoc 预约容量提醒"
    assert "预约名额现已约满" in full_body
