# Database migrations

Production openGauss/GaussDB deployments use Flask-Migrate/Alembic. Apply the
v7 revision during a maintenance window after taking the database and permanent
asset backup:

```powershell
$env:FLASK_APP = "run:app"
flask db upgrade 20260720_schema_v7
```

SQLite must continue to use `scripts/upgrade_local_database.py`; do not run this
revision against the local SQLite file.
