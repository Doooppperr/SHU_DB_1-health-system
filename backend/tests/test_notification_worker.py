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
