import sqlite3
from contextlib import closing

from sqlalchemy import create_engine

from app import models as _models  # noqa: F401
from app.extensions import db
from scripts.upgrade_local_database import (
    SCHEMA_VERSION,
    inspect_schema,
    rebuild_database,
)


def _create_legacy_database(path):
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    try:
        db.metadata.create_all(engine)
    finally:
        engine.dispose()

    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("DROP TABLE institution_invites")
        connection.execute("DROP TABLE institution_images")
        connection.execute("ALTER TABLE institutions DROP COLUMN is_active")
        connection.execute("ALTER TABLE packages DROP COLUMN is_active")

        # Recreate users with the legacy two-role CHECK and without the new
        # institution binding. Empty dependent tables may retain the temporary
        # FK name; the upgrader builds all target FKs from current metadata.
        connection.execute("ALTER TABLE users RENAME TO users_v2")
        connection.execute(
            """
            CREATE TABLE users (
                id INTEGER NOT NULL PRIMARY KEY,
                username VARCHAR(80) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                email VARCHAR(120) UNIQUE,
                phone VARCHAR(30),
                role VARCHAR(20) NOT NULL,
                created_at DATETIME NOT NULL,
                CONSTRAINT ck_users_role CHECK (role in ('user', 'admin')),
                CONSTRAINT ck_users_username_not_blank
                    CHECK (length(trim(username)) > 0)
            )
            """
        )
        connection.execute("DROP TABLE users_v2")

        connection.execute(
            """
            INSERT INTO institutions
                (id, name, branch_name, address, district, logo_url)
            VALUES
                (11, '测试体检中心', '总院', '健康路 1 号', '测试区',
                 '/uploads/institutions/legacy-cover.png')
            """
        )
        connection.execute(
            """
            INSERT INTO packages
                (id, institution_id, name, focus_area, gender_scope, price)
            VALUES
                (21, 11, '基础套餐', '基础筛查', 'all', 99.00)
            """
        )
        connection.execute(
            """
            INSERT INTO users
                (id, username, password_hash, email, role, created_at)
            VALUES
                (31, 'legacy-admin', 'preserved-password-hash',
                 'legacy@example.com', 'admin', CURRENT_TIMESTAMP)
            """
        )
        connection.execute("PRAGMA user_version=0")
        connection.commit()


def test_schema_v2_migration_preserves_rows_and_migrates_logo(tmp_path):
    database_path = tmp_path / "legacy.db"
    _create_legacy_database(database_path)

    backup_path = rebuild_database(database_path)

    assert backup_path is not None
    assert backup_path.is_file()
    assert ".before-schema-v2-" in backup_path.name

    with closing(sqlite3.connect(database_path)) as connection:
        report = inspect_schema(connection)
        assert report.is_current
        assert report.version == SCHEMA_VERSION
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute(
            "SELECT id, role, managed_institution_id, password_hash FROM users"
        ).fetchall() == [(31, "admin", None, "preserved-password-hash")]
        assert connection.execute(
            "SELECT id, is_active FROM institutions"
        ).fetchall() == [(11, 1)]
        assert connection.execute(
            "SELECT id, institution_id, is_active FROM packages"
        ).fetchall() == [(21, 11, 1)]
        assert connection.execute(
            """
            SELECT institution_id, storage_key, image_url, sort_order
            FROM institution_images
            """
        ).fetchall() == [
            (
                11,
                "institutions/legacy-cover.png",
                "/uploads/institutions/legacy-cover.png",
                0,
            )
        ]
        assert connection.execute(
            "SELECT COUNT(*) FROM institution_invites"
        ).fetchone()[0] == 0

    # A second execution validates in place and creates no extra backup.
    backups_before = set(tmp_path.glob("legacy.before-schema-v2-*.db"))
    assert rebuild_database(database_path) is None
    assert set(tmp_path.glob("legacy.before-schema-v2-*.db")) == backups_before

    # The backup is the untouched legacy file.
    with closing(sqlite3.connect(backup_path)) as backup:
        assert backup.execute("PRAGMA user_version").fetchone()[0] == 0
        assert backup.execute("SELECT id FROM users").fetchall() == [(31,)]


def test_check_inspection_does_not_mutate_legacy_database(tmp_path):
    database_path = tmp_path / "legacy-check.db"
    _create_legacy_database(database_path)
    before = database_path.read_bytes()

    with closing(sqlite3.connect(database_path)) as connection:
        report = inspect_schema(connection)

    assert report.version == 0
    assert report.is_current is False
    assert "institution_images" in report.missing_tables
    assert "institution_invites" in report.missing_tables
    assert "users.managed_institution_id" in report.missing_columns
    assert database_path.read_bytes() == before
