from flask import Blueprint


organizations_bp = Blueprint("organizations", __name__)

from . import routes  # noqa: E402,F401
