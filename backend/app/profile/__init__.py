from flask import Blueprint

profile_bp = Blueprint("profile", __name__)

from . import routes  # noqa: E402,F401
