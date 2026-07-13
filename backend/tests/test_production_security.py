import pytest
from flask import Flask

from app import _validate_runtime_security, create_app
from app.config import DevelopmentConfig, ProductionConfig
from app.extensions import db
from app.models import User


def test_production_requires_an_explicit_strong_jwt_secret():
    app = Flask(__name__)
    app.config["JWT_SECRET_KEY"] = ""
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        _validate_runtime_security(app, "production")

    app.config["JWT_SECRET_KEY"] = "x" * 48
    _validate_runtime_security(app, "production")


def test_production_rotates_the_known_demo_admin_password(tmp_path, monkeypatch):
    database_path = (tmp_path / "production-security.db").resolve()
    database_uri = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setattr(DevelopmentConfig, "SQLALCHEMY_DATABASE_URI", database_uri)
    monkeypatch.setenv("DEFAULT_ADMIN_USERNAME", "admin")
    monkeypatch.delenv("DEFAULT_ADMIN_PASSWORD", raising=False)

    development_app = create_app("development")
    with development_app.app_context():
        admin = User.query.filter_by(username="admin").one()
        assert admin.check_password("admin123")
        db.session.remove()
        db.engine.dispose()

    strong_password = "Local-Demo-Admin-2026!"
    monkeypatch.setattr(ProductionConfig, "SQLALCHEMY_DATABASE_URI", database_uri)
    monkeypatch.setattr(ProductionConfig, "JWT_SECRET_KEY", "j" * 48)
    monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", strong_password)

    production_app = create_app("production")
    with production_app.app_context():
        admin = User.query.filter_by(username="admin").one()
        assert admin.check_password(strong_password)
        assert not admin.check_password("admin123")
        db.session.remove()
        db.engine.dispose()

    local_database_path = (tmp_path / "loopback-demo.db").resolve()
    monkeypatch.setattr(
        ProductionConfig,
        "SQLALCHEMY_DATABASE_URI",
        f"sqlite:///{local_database_path.as_posix()}",
    )
    monkeypatch.setenv("ALLOW_INSECURE_LOCAL_DEMO", "1")
    monkeypatch.delenv("DEFAULT_ADMIN_PASSWORD", raising=False)

    local_demo_app = create_app("production")
    with local_demo_app.app_context():
        admin = User.query.filter_by(username="admin").one()
        assert admin.check_password("admin123")
        db.session.remove()
        db.engine.dispose()
