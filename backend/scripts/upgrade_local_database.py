"""Upgrade a legacy local SQLite database to schema v2.

SQLite cannot replace CHECK constraints or add all required constraints with a
portable ``ALTER TABLE`` sequence.  The upgrader therefore builds the current
SQLAlchemy schema in a neighbouring file, copies the legacy rows using the
intersection of old/new columns, applies explicit values for new columns,
validates the result, creates a backup, and atomically replaces the source.

The script is deliberately safe to run more than once.  A valid v2 database is
only checked; it is not rebuilt and no additional backup is created.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from sqlalchemy import create_engine


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = BACKEND_DIR / "instance" / "health_system.db"
SCHEMA_VERSION = 2
NEW_V2_TABLES = {"institution_invites", "institution_images"}
NEW_COLUMN_DEFAULTS = {
    ("users", "managed_institution_id"): None,
    ("institutions", "is_active"): 1,
    ("packages", "is_active"): 1,
}

sys.path.insert(0, str(BACKEND_DIR))

from app import models as _models  # noqa: E402,F401
from app.extensions import db  # noqa: E402


@dataclass(frozen=True)
class CopySnapshot:
    counts: dict[str, int]
    primary_keys: dict[str, tuple[tuple[object, ...], ...]]


@dataclass(frozen=True)
class SchemaReport:
    version: int
    missing_tables: tuple[str, ...]
    missing_columns: tuple[str, ...]
    missing_constraints: tuple[str, ...]

    @property
    def is_current(self) -> bool:
        return (
            self.version == SCHEMA_VERSION
            and not self.missing_tables
            and not self.missing_columns
            and not self.missing_constraints
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upgrade the local SQLite database to schema v2."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
        help=f"SQLite file to upgrade (default: {DEFAULT_DATABASE}).",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Report schema state without modifying the database.",
    )
    return parser.parse_args()


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    quoted_table = _quote_identifier(table_name)
    return {
        row[1]
        for row in connection.execute(f"PRAGMA table_info({quoted_table})")
    }


def expected_named_constraints() -> set[str]:
    return {
        constraint.name
        for table in db.metadata.tables.values()
        for constraint in table.constraints
        if constraint.name
    }


def database_ddl(connection: sqlite3.Connection) -> str:
    rows = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type IN ('table', 'index')
          AND name NOT LIKE 'sqlite_%'
          AND sql IS NOT NULL
        """
    )
    return "\n".join(row[0] for row in rows)


def missing_constraints(connection: sqlite3.Connection) -> list[str]:
    ddl = database_ddl(connection)
    return sorted(name for name in expected_named_constraints() if name not in ddl)


def inspect_schema(connection: sqlite3.Connection) -> SchemaReport:
    tables = _table_names(connection)
    expected_tables = set(db.metadata.tables)
    missing_tables = sorted(expected_tables - tables)
    missing_columns: list[str] = []
    for table_name in sorted(expected_tables & tables):
        actual_columns = _table_columns(connection, table_name)
        for column in db.metadata.tables[table_name].columns:
            if column.name not in actual_columns:
                missing_columns.append(f"{table_name}.{column.name}")

    return SchemaReport(
        version=int(connection.execute("PRAGMA user_version").fetchone()[0]),
        missing_tables=tuple(missing_tables),
        missing_columns=tuple(missing_columns),
        missing_constraints=tuple(missing_constraints(connection)),
    )


def _primary_key_rows(
    connection: sqlite3.Connection,
    table_name: str,
) -> tuple[tuple[object, ...], ...]:
    table = db.metadata.tables[table_name]
    primary_keys = [column.name for column in table.primary_key.columns]
    if not primary_keys:
        return ()
    quoted_columns = ", ".join(_quote_identifier(name) for name in primary_keys)
    quoted_table = _quote_identifier(table_name)
    rows = connection.execute(
        f"SELECT {quoted_columns} FROM {quoted_table} ORDER BY {quoted_columns}"
    ).fetchall()
    return tuple(tuple(row) for row in rows)


def snapshot_database(connection: sqlite3.Connection) -> CopySnapshot:
    tables = _table_names(connection)
    counts: dict[str, int] = {}
    primary_keys: dict[str, tuple[tuple[object, ...], ...]] = {}
    for table_name in db.metadata.tables:
        if table_name not in tables:
            continue
        quoted_table = _quote_identifier(table_name)
        counts[table_name] = int(
            connection.execute(f"SELECT COUNT(*) FROM {quoted_table}").fetchone()[0]
        )
        primary_keys[table_name] = _primary_key_rows(connection, table_name)
    return CopySnapshot(counts=counts, primary_keys=primary_keys)


def validate_database(
    connection: sqlite3.Connection,
    expected: CopySnapshot,
) -> None:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise RuntimeError(f"SQLite integrity_check failed: {integrity}")

    foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_errors:
        raise RuntimeError(
            f"SQLite foreign_key_check found {len(foreign_key_errors)} violation(s)."
        )

    report = inspect_schema(connection)
    if not report.is_current:
        details = []
        if report.version != SCHEMA_VERSION:
            details.append(f"version={report.version}")
        if report.missing_tables:
            details.append(f"missing tables={', '.join(report.missing_tables)}")
        if report.missing_columns:
            details.append(f"missing columns={', '.join(report.missing_columns)}")
        if report.missing_constraints:
            details.append(
                f"missing constraints={', '.join(report.missing_constraints)}"
            )
        raise RuntimeError("Schema v2 validation failed: " + "; ".join(details))

    for table_name, expected_count in expected.counts.items():
        quoted_table = _quote_identifier(table_name)
        actual_count = int(
            connection.execute(f"SELECT COUNT(*) FROM {quoted_table}").fetchone()[0]
        )
        if actual_count != expected_count:
            raise RuntimeError(
                f"Row count mismatch for {table_name}: "
                f"expected {expected_count}, got {actual_count}."
            )

        actual_primary_keys = _primary_key_rows(connection, table_name)
        expected_primary_keys = expected.primary_keys.get(table_name, ())
        if actual_primary_keys != expected_primary_keys:
            raise RuntimeError(f"Primary-key mismatch for {table_name}.")


def _copy_table_rows(
    source: sqlite3.Connection,
    target: sqlite3.Connection,
    table_name: str,
) -> None:
    table = db.metadata.tables[table_name]
    source_columns = _table_columns(source, table_name)
    copied_columns: list[str] = []
    missing_required: list[str] = []
    for column in table.columns:
        key = (table_name, column.name)
        if column.name in source_columns or key in NEW_COLUMN_DEFAULTS or column.nullable:
            copied_columns.append(column.name)
        elif column.server_default is None:
            missing_required.append(column.name)

    if missing_required:
        raise RuntimeError(
            f"Source table {table_name} is missing required column(s): "
            f"{', '.join(missing_required)}"
        )

    source_select_columns = [
        column_name for column_name in copied_columns if column_name in source_columns
    ]
    quoted_source_columns = ", ".join(
        _quote_identifier(name) for name in source_select_columns
    )
    quoted_table = _quote_identifier(table_name)
    primary_keys = [column.name for column in table.primary_key.columns]
    order_by = ", ".join(_quote_identifier(name) for name in primary_keys) or "rowid"
    rows = source.execute(
        f"SELECT {quoted_source_columns} FROM {quoted_table} ORDER BY {order_by}"
    ).fetchall()

    if not rows:
        return

    source_indexes = {
        column_name: index for index, column_name in enumerate(source_select_columns)
    }
    insert_rows = []
    for row in rows:
        values = []
        for column_name in copied_columns:
            if column_name in source_indexes:
                values.append(row[source_indexes[column_name]])
            else:
                values.append(NEW_COLUMN_DEFAULTS.get((table_name, column_name)))
        insert_rows.append(tuple(values))

    quoted_insert_columns = ", ".join(
        _quote_identifier(name) for name in copied_columns
    )
    placeholders = ", ".join("?" for _ in copied_columns)
    target.executemany(
        f"INSERT INTO {quoted_table} ({quoted_insert_columns}) "
        f"VALUES ({placeholders})",
        insert_rows,
    )


def _legacy_storage_key(institution_id: int, logo_url: str) -> str:
    parsed = urlsplit(logo_url)
    path = unquote(parsed.path).replace("\\", "/")
    normalized = path.lstrip("/")
    if normalized.startswith("uploads/"):
        normalized = normalized[len("uploads/") :]
    if normalized and not parsed.scheme and ".." not in PurePosixPath(normalized).parts:
        return normalized

    filename = PurePosixPath(path).name or f"logo-{institution_id}"
    return f"legacy/institution-{institution_id}/{filename}"


def _migrate_legacy_logos(
    target: sqlite3.Connection,
    source_had_images_table: bool,
) -> int:
    """Create a first gallery image from legacy ``institutions.logo_url``."""

    migrated = 0
    rows = target.execute(
        """
        SELECT id, logo_url
        FROM institutions
        WHERE logo_url IS NOT NULL AND length(trim(logo_url)) > 0
        ORDER BY id
        """
    ).fetchall()
    for institution_id, logo_url in rows:
        # Existing v2 image rows win when repairing a partially current schema.
        if source_had_images_table:
            existing = target.execute(
                "SELECT 1 FROM institution_images WHERE institution_id = ? LIMIT 1",
                (institution_id,),
            ).fetchone()
            if existing:
                continue
        target.execute(
            """
            INSERT INTO institution_images
                (institution_id, storage_key, image_url, sort_order, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (
                institution_id,
                _legacy_storage_key(institution_id, logo_url.strip()),
                logo_url.strip(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        migrated += 1
    return migrated


def copy_rows(
    source: sqlite3.Connection,
    target: sqlite3.Connection,
) -> CopySnapshot:
    source_tables = _table_names(source)
    expected_legacy_tables = set(db.metadata.tables) - NEW_V2_TABLES
    missing_legacy_tables = sorted(expected_legacy_tables - source_tables)
    if missing_legacy_tables:
        raise RuntimeError(
            "Source database is missing legacy table(s): "
            + ", ".join(missing_legacy_tables)
        )

    source_snapshot = snapshot_database(source)

    target.execute("PRAGMA foreign_keys=OFF")
    target.execute("BEGIN")
    try:
        for table in db.metadata.sorted_tables:
            if table.name not in source_tables:
                continue
            _copy_table_rows(source, target, table.name)

        _migrate_legacy_logos(
            target,
            source_had_images_table="institution_images" in source_tables,
        )
        target.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        target.commit()
    except Exception:
        target.rollback()
        raise
    finally:
        target.execute("PRAGMA foreign_keys=ON")

    target_snapshot = snapshot_database(target)
    # Existing tables must preserve their source counts and primary keys
    # exactly. New v2 tables use their post-copy snapshot because legacy logo
    # rows are intentionally materialized as new InstitutionImage records.
    expected_counts = dict(source_snapshot.counts)
    expected_primary_keys = dict(source_snapshot.primary_keys)
    for table_name in NEW_V2_TABLES:
        expected_counts[table_name] = target_snapshot.counts.get(table_name, 0)
        expected_primary_keys[table_name] = target_snapshot.primary_keys.get(
            table_name,
            (),
        )
    return CopySnapshot(
        counts=expected_counts,
        primary_keys=expected_primary_keys,
    )


def _validate_source(connection: sqlite3.Connection) -> None:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise RuntimeError(f"Source SQLite integrity_check failed: {integrity}")
    foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_errors:
        raise RuntimeError(
            f"Source database has {len(foreign_key_errors)} foreign key violation(s)."
        )


def _create_backup_path(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = database_path.with_name(
        f"{database_path.stem}.before-schema-v2-{timestamp}.db"
    )
    if not candidate.exists():
        return candidate
    return database_path.with_name(
        f"{database_path.stem}.before-schema-v2-{timestamp}-{uuid.uuid4().hex[:8]}.db"
    )


def rebuild_database(database_path: Path) -> Path | None:
    database_path = database_path.resolve()
    if not database_path.is_file():
        raise FileNotFoundError(f"SQLite database not found: {database_path}")

    with closing(sqlite3.connect(database_path)) as current:
        _validate_source(current)
        current_report = inspect_schema(current)
        if current_report.is_current:
            validate_database(current, snapshot_database(current))
            return None

    temporary_path = database_path.with_name(
        f".{database_path.stem}.upgrade-{uuid.uuid4().hex}.db"
    )
    backup_path = _create_backup_path(database_path)

    source_snapshot: CopySnapshot | None = None
    source = sqlite3.connect(database_path)
    try:
        _validate_source(source)
        source_snapshot = snapshot_database(source)

        engine = create_engine(f"sqlite:///{temporary_path.as_posix()}")
        try:
            db.metadata.create_all(engine)
        finally:
            engine.dispose()

        target = sqlite3.connect(temporary_path)
        try:
            expected = copy_rows(source, target)
            validate_database(target, expected)
            target.execute("VACUUM")
        finally:
            target.close()
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    finally:
        source.close()

    try:
        shutil.copy2(database_path, backup_path)
        with closing(sqlite3.connect(backup_path)) as backup:
            _validate_source(backup)
            if snapshot_database(backup) != source_snapshot:
                raise RuntimeError("Backup verification failed: copied rows differ.")
        os.replace(temporary_path, database_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        backup_path.unlink(missing_ok=True)
        raise
    return backup_path


def _print_report(database_path: Path, report: SchemaReport) -> None:
    print(f"database={database_path}")
    print(f"user_version={report.version}")
    print(f"expected_user_version={SCHEMA_VERSION}")
    print(f"schema_current={'yes' if report.is_current else 'no'}")
    print(f"missing_tables={len(report.missing_tables)}")
    for item in report.missing_tables:
        print(f"table:{item}")
    print(f"missing_columns={len(report.missing_columns)}")
    for item in report.missing_columns:
        print(f"column:{item}")
    print(f"missing_constraints={len(report.missing_constraints)}")
    for item in report.missing_constraints:
        print(f"constraint:{item}")


def main() -> None:
    args = parse_args()
    database_path = args.database.resolve()
    if not database_path.is_file():
        raise FileNotFoundError(f"SQLite database not found: {database_path}")

    if args.check_only:
        with closing(sqlite3.connect(database_path)) as connection:
            _validate_source(connection)
            report = inspect_schema(connection)
        _print_report(database_path, report)
        return

    backup_path = rebuild_database(database_path)
    print(f"database={database_path}")
    if backup_path is None:
        print("schema_upgrade=already-current")
    else:
        print(f"backup={backup_path}")
        print("schema_upgrade=ok")


if __name__ == "__main__":
    main()
