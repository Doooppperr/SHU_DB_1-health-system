"""Deliver notification_outbox rows with retry-safe idempotent state transitions."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import json
from pathlib import Path
import smtplib
import sys
import time

from sqlalchemy import update

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import NotificationDelivery, NotificationOutbox  # noqa: E402


def _send(app, row):
    subject = {"booking_group_created": "新的体检预约组",
               "appointment_date_full": "体检日期已约满",
               "waitlist_available": "您关注的体检日期出现可预约名额"}.get(row.event_type, "康康健健通知")
    recipient = app.config.get("NOTIFICATION_EMAIL_REDIRECT") or row.recipient
    message = EmailMessage(); message["Subject"] = subject
    message["From"] = app.config["SMTP_FROM"]; message["To"] = recipient
    message.set_content(json.dumps(row.payload, ensure_ascii=False, indent=2))
    if app.config["NOTIFICATION_EMAIL_DRY_RUN"]:
        return f"dry-run-{row.id}"
    if not app.config["SMTP_HOST"]:
        raise RuntimeError("SMTP_HOST is not configured")
    with smtplib.SMTP(app.config["SMTP_HOST"], app.config["SMTP_PORT"], timeout=20) as client:
        if app.config["SMTP_USE_TLS"]: client.starttls()
        if app.config["SMTP_USERNAME"]: client.login(app.config["SMTP_USERNAME"], app.config["SMTP_PASSWORD"])
        response = client.send_message(message)
    return str(response or f"smtp-{row.id}")


def run_batch(app, limit=50):
    now = datetime.now(timezone.utc)
    row_ids = [
        row_id
        for (row_id,) in db.session.query(NotificationOutbox.id)
        .filter(
            NotificationOutbox.status.in_(("pending", "failed")),
            NotificationOutbox.next_attempt_at <= now,
        )
        .order_by(NotificationOutbox.id)
        .limit(limit)
        .all()
    ]
    delivered = 0
    attempted = 0
    for row_id in row_ids:
        # Claim with a conditional UPDATE so accidentally starting two workers
        # cannot send the same Outbox row twice.
        claim = db.session.execute(
            update(NotificationOutbox)
            .where(
                NotificationOutbox.id == row_id,
                NotificationOutbox.status.in_(("pending", "failed")),
                NotificationOutbox.next_attempt_at <= now,
            )
            .values(
                status="sending",
                attempts=NotificationOutbox.attempts + 1,
            )
            .execution_options(synchronize_session=False)
        )
        db.session.commit()
        if claim.rowcount != 1:
            continue
        attempted += 1
        row = db.session.get(NotificationOutbox, row_id)
        try:
            provider_id = _send(app, row)
            row.status = "sent"; row.sent_at = datetime.now(timezone.utc)
            db.session.add(NotificationDelivery(outbox_id=row.id, success=True, provider_message_id=provider_id))
            delivered += 1
        except Exception as exc:
            row.status = "failed"
            row.next_attempt_at = datetime.now(timezone.utc) + timedelta(minutes=min(2 ** row.attempts, 60))
            db.session.add(NotificationDelivery(outbox_id=row.id, success=False, error_message=str(exc)[:500]))
        db.session.commit()
    return attempted, delivered


def run_watch(app, limit=50, interval_seconds=5, *, max_cycles=None, sleep=time.sleep):
    """Continuously drain the Outbox; ``max_cycles`` exists for deterministic tests."""
    cycles = 0
    totals = [0, 0]
    while max_cycles is None or cycles < max_cycles:
        with app.app_context():
            attempted, delivered = run_batch(app, limit)
        totals[0] += attempted
        totals[1] += delivered
        if attempted:
            print(
                f"notification_batch attempted={attempted} delivered={delivered}",
                flush=True,
            )
        cycles += 1
        if max_cycles is not None and cycles >= max_cycles:
            break
        sleep(interval_seconds)
    return tuple(totals)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=5)
    parser.add_argument("--config", choices=("development", "production"), default="development")
    args = parser.parse_args()
    app = create_app(args.config)
    limit = max(1, min(args.limit, 500))
    if args.watch:
        interval = max(1.0, min(args.interval_seconds, 300.0))
        print(f"notification_worker=watching interval_seconds={interval:g}", flush=True)
        try:
            run_watch(app, limit, interval)
        except KeyboardInterrupt:
            print("notification_worker=stopped", flush=True)
        return
    with app.app_context():
        attempted, delivered = run_batch(app, limit)
    print(f"attempted={attempted} delivered={delivered}")


if __name__ == "__main__": main()
