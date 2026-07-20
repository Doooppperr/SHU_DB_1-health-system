from flask import Blueprint

health_data_v7_bp = Blueprint("health_data_v7", __name__)

from . import routes  # noqa: E402,F401
