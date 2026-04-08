import pytest

from app import create_app
from app.extensions import db
from app.seed import seed_core_data


@pytest.fixture()
def app():
    app = create_app("testing")

    with app.app_context():
        db.drop_all()
        db.create_all()
        seed_core_data()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
