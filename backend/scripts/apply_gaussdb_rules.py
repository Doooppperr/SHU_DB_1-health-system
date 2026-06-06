"""Apply database-level rules for the GaussDB/openGauss runtime database.

The Flask models create tables and ordinary constraints for fresh databases.
This script is for an existing cloud database: it adds missing CHECK
constraints and trigger-based rules without recreating user data.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = BACKEND_DIR / ".env"


CHECK_CONSTRAINTS = [
    ("users", "ck_users_role", "role in ('user', 'admin')"),
    ("users", "ck_users_username_not_blank", "length(trim(username)) > 0"),
    ("friend_relations", "ck_friend_not_self", "user_id <> friend_user_id"),
    ("friend_relations", "ck_friend_relation_name_not_blank", "length(trim(relation_name)) > 0"),
    ("comments", "ck_comments_rating_range", "rating between 1 and 5"),
    ("comments", "ck_comments_content_not_blank", "length(trim(content)) > 0"),
    ("indicator_categories", "ck_indicator_categories_name_not_blank", "length(trim(name)) > 0"),
    ("indicator_dicts", "ck_indicator_dicts_code_not_blank", "length(trim(code)) > 0"),
    ("indicator_dicts", "ck_indicator_dicts_name_not_blank", "length(trim(name)) > 0"),
    ("indicator_dicts", "ck_indicator_dicts_value_type", "value_type in ('numeric', 'text')"),
    (
        "indicator_dicts",
        "ck_indicator_dicts_reference_range",
        "reference_low is null or reference_high is null or reference_low <= reference_high",
    ),
    ("institutions", "ck_institutions_name_not_blank", "length(trim(name)) > 0"),
    ("institutions", "ck_institutions_branch_not_blank", "length(trim(branch_name)) > 0"),
    ("institutions", "ck_institutions_address_not_blank", "length(trim(address)) > 0"),
    ("institutions", "ck_institutions_district_not_blank", "length(trim(district)) > 0"),
    ("packages", "ck_packages_name_not_blank", "length(trim(name)) > 0"),
    ("packages", "ck_packages_focus_area_not_blank", "length(trim(focus_area)) > 0"),
    ("packages", "ck_packages_gender_scope", "gender_scope in ('all', 'male', 'female', 'female_all')"),
    ("packages", "ck_packages_price_non_negative", "price >= 0"),
    ("health_records", "ck_health_records_status", "status in ('draft', 'parsed', 'confirmed')"),
    ("health_indicators", "ck_health_indicators_value_not_blank", "length(trim(value)) > 0"),
    ("health_indicators", "ck_health_indicators_source", "source in ('manual', 'ocr')"),
]


FUNCTION_SQL = [
    """
    CREATE OR REPLACE FUNCTION enforce_health_record_package_match()
    RETURNS trigger AS $$
    DECLARE
        package_institution_id integer;
    BEGIN
        IF NEW.package_id IS NULL THEN
            RETURN NEW;
        END IF;

        SELECT institution_id
          INTO package_institution_id
          FROM packages
         WHERE id = NEW.package_id;

        IF package_institution_id IS NULL THEN
            RETURN NEW;
        END IF;

        IF NEW.institution_id IS NULL THEN
            NEW.institution_id := package_institution_id;
            RETURN NEW;
        END IF;

        IF NEW.institution_id <> package_institution_id THEN
            RAISE EXCEPTION 'package_id % does not belong to institution_id %', NEW.package_id, NEW.institution_id;
        END IF;

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    CREATE OR REPLACE FUNCTION enforce_comment_requires_record()
    RETURNS trigger AS $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
              FROM health_records
             WHERE uploader_id = NEW.user_id
               AND institution_id = NEW.institution_id
        ) THEN
            RAISE EXCEPTION 'user_id % must upload a record for institution_id % before commenting',
                NEW.user_id, NEW.institution_id;
        END IF;

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    CREATE OR REPLACE FUNCTION set_health_indicator_abnormal_flag()
    RETURNS trigger AS $$
    DECLARE
        dict_value_type text;
        dict_reference_low numeric;
        dict_reference_high numeric;
        numeric_value numeric;
    BEGIN
        SELECT value_type, reference_low, reference_high
          INTO dict_value_type, dict_reference_low, dict_reference_high
          FROM indicator_dicts
         WHERE id = NEW.indicator_dict_id;

        IF dict_value_type <> 'numeric' THEN
            NEW.is_abnormal := false;
            RETURN NEW;
        END IF;

        BEGIN
            numeric_value := replace(trim(NEW.value), ',', '')::numeric;
        EXCEPTION WHEN others THEN
            NEW.is_abnormal := false;
            RETURN NEW;
        END;

        NEW.is_abnormal := (
            (dict_reference_low IS NOT NULL AND numeric_value < dict_reference_low)
            OR
            (dict_reference_high IS NOT NULL AND numeric_value > dict_reference_high)
        );

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """,
]


TRIGGERS = [
    (
        "trg_health_records_package_match",
        "health_records",
        """
        CREATE TRIGGER trg_health_records_package_match
        BEFORE INSERT OR UPDATE OF institution_id, package_id
        ON health_records
        FOR EACH ROW
        EXECUTE PROCEDURE enforce_health_record_package_match()
        """,
    ),
    (
        "trg_comments_require_uploaded_record",
        "comments",
        """
        CREATE TRIGGER trg_comments_require_uploaded_record
        BEFORE INSERT OR UPDATE OF user_id, institution_id
        ON comments
        FOR EACH ROW
        EXECUTE PROCEDURE enforce_comment_requires_record()
        """,
    ),
    (
        "trg_health_indicators_set_abnormal",
        "health_indicators",
        """
        CREATE TRIGGER trg_health_indicators_set_abnormal
        BEFORE INSERT OR UPDATE OF value, indicator_dict_id
        ON health_indicators
        FOR EACH ROW
        EXECUTE PROCEDURE set_health_indicator_abnormal_flag()
        """,
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply GaussDB CHECK constraints and triggers.")
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL from .env.")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH), help="Path to .env file.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned changes without applying them.")
    return parser.parse_args()


def constraint_exists(conn, name: str) -> bool:
    return bool(
        conn.execute(
            text("select 1 from pg_constraint where conname = :name"),
            {"name": name},
        ).first()
    )


def trigger_exists(conn, name: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                select 1
                  from pg_trigger
                 where tgname = :name
                   and not tgisinternal
                """
            ),
            {"name": name},
        ).first()
    )


def apply_rules(database_url: str, dry_run: bool = False) -> None:
    engine = create_engine(database_url, future=True)
    planned: list[str] = []

    with engine.begin() as conn:
        for table_name, constraint_name, expression in CHECK_CONSTRAINTS:
            if constraint_exists(conn, constraint_name):
                continue
            sql = f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} CHECK ({expression})"
            planned.append(sql)
            if not dry_run:
                conn.execute(text(sql))

        for sql in FUNCTION_SQL:
            planned.append(sql.strip())
            if not dry_run:
                conn.execute(text(sql))

        for trigger_name, _table_name, sql in TRIGGERS:
            if trigger_exists(conn, trigger_name):
                continue
            planned.append(sql.strip())
            if not dry_run:
                conn.execute(text(sql))

    if planned:
        print(f"planned_changes={len(planned)}")
        for item in planned:
            first_line = item.strip().splitlines()[0]
            print(first_line)
    else:
        print("planned_changes=0")


def main() -> None:
    args = parse_args()
    load_dotenv(args.env_file)
    database_url = args.database_url or os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required.")

    apply_rules(database_url, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
