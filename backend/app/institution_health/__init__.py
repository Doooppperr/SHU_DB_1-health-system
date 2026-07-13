from flask import Blueprint


institution_health_bp = Blueprint("institution_health", __name__)

from . import routes  # noqa: E402,F401
