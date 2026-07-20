# HealthDoc 1.0—3.0 database migrations

HealthDoc 1.0 established the initial account, institution, appointment and
health-record schema. The 2.0 work evolved that model into schema v6 with
self-measurements, institution report lifecycle and authorization boundaries.
HealthDoc 3.0 first introduced schema v7 for health domains, package versions,
group bookings, waitlists and richer report results, then schema v8 for
organization/branch collaboration and cross-branch access auditing.

The current production baseline is schema v8. Production openGauss/GaussDB
deployments use Flask-Migrate/Alembic and must be upgraded during a maintenance
window after backing up the database, permanent uploads and environment file:

```powershell
$env:FLASK_APP = "run:app"
flask db upgrade 20260720_schema_v8
```

The v8 revision depends on the v7 revision, so Alembic applies both when an
older production database requires them. Never use `db.create_all()` as a
replacement for production migration.

SQLite uses `scripts/upgrade_local_database.py` and `PRAGMA user_version=8`;
do not run the Alembic revision against the local SQLite file. The synthetic
demo reset is also not a migration tool and must never target production.
