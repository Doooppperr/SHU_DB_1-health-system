from flask import Blueprint


indicators_bp = Blueprint("indicators", __name__)

from . import routes  # noqa: E402,F401
