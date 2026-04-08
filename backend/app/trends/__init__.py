from flask import Blueprint


trends_bp = Blueprint("trends", __name__)

from . import routes  # noqa: E402,F401
