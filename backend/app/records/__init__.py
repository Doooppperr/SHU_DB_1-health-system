from flask import Blueprint


records_bp = Blueprint("records", __name__)

from . import routes  # noqa: E402,F401
