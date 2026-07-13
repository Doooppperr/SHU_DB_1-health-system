from flask import Blueprint


org_bp = Blueprint("org", __name__)

from . import routes  # noqa: E402,F401
