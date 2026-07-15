import sqlite3
from datetime import datetime, timezone

from app.extensions import db
from app.models import ExamRegistration, InstitutionReport, ReportIndicator, SelfMeasurement, User
from app.schema import CURRENT_SCHEMA_VERSION


def test_schema_v3_replaces_legacy_record_tables(app):
    with app.app_context():
        assert CURRENT_SCHEMA_VERSION == 3
        assert {"self_measurements", "exam_registrations", "institution_reports", "report_indicators"} <= set(db.metadata.tables)
        assert "health_records" not in db.metadata.tables
        assert "health_indicators" not in db.metadata.tables
        connection = db.session.connection()
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []


def test_rebuild_preserves_only_admin_identity_and_password(tmp_path):
    from scripts.upgrade_local_database import rebuild_database

    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, email TEXT, phone TEXT, role TEXT, created_at TEXT)")
    connection.execute("INSERT INTO users VALUES (7, 'admin', 'unchanged-hash', 'a@example.com', NULL, 'admin', '2020-01-01')")
    connection.execute("INSERT INTO users VALUES (8, 'legacy-user', 'discard-me', NULL, NULL, 'user', '2020-01-01')")
    connection.commit(); connection.close()
    backup = rebuild_database(path)
    assert backup and backup.exists()
    connection = sqlite3.connect(path)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
    assert connection.execute("SELECT id, username, password_hash FROM users").fetchall() == [(7, "admin", "unchanged-hash")]
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    connection.close()


def test_deleting_institution_account_retains_report_snapshot(app, client):
    admin = login(client, "admin", "admin123")
    with app.app_context():
        staff = User.query.filter_by(username="institution1_staff1").first()
        report = InstitutionReport.query.filter_by(created_by_user_id=staff.id).first()
        staff_id, report_id, username = staff.id, report.id, staff.username
    response = client.delete(f"/api/admin/institution-accounts/{staff_id}", headers=admin)
    assert response.status_code == 200
    with app.app_context():
        report = db.session.get(InstitutionReport, report_id)
        assert report.created_by_user_id is None
        assert report.created_by_username_snapshot == username


def test_demo_seed_has_rich_timelines_and_complete_role_matrix(app):
    with app.app_context():
        people = User.query.filter_by(role="user").order_by(User.username).all()
        assert [user.username for user in people] == [
            "test1", "test2", "test3", "test4", "test5"
        ]
        assert User.query.filter_by(role="institution_admin").count() == 6
        assert User.query.filter_by(username="demo_admin", role="admin").count() == 1
        assert SelfMeasurement.query.count() == 138
        assert ExamRegistration.query.count() == 20
        assert InstitutionReport.query.count() == 12
        assert ReportIndicator.query.count() == 72
        for user in people:
            assert SelfMeasurement.query.filter_by(user_id=user.id).count() >= 27
            assert InstitutionReport.query.filter_by(
                matched_user_id=user.id, status="published"
            ).count() >= 2


def test_full_snapshot_migration_restores_bidirectional_report_links(app, tmp_path):
    from scripts.migrate_sqlite_to_gaussdb import migrate

    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    with app.app_context():
        source = sqlite3.connect(source_path)
        raw_connection = db.engine.raw_connection()
        try:
            raw_connection.driver_connection.backup(source)
        finally:
            source.close()
            raw_connection.close()

    counts = migrate(
        source_path,
        f"sqlite:///{target_path.as_posix()}",
        replace=True,
    )
    assert counts["exam_registrations"] == 20
    assert counts["institution_reports"] == 12

    connection = sqlite3.connect(target_path)
    try:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        broken_links = connection.execute(
            "SELECT COUNT(*) FROM exam_registrations AS registration "
            "JOIN institution_reports AS report "
            "ON report.id = registration.matched_report_id "
            "WHERE report.exam_registration_id <> registration.id"
        ).fetchone()[0]
        assert broken_links == 0
    finally:
        connection.close()


def login(client, username, password):
    response = client.post("/api/auth/login", json=client.login_payload(username, password))
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.get_json()['access_token']}"}
