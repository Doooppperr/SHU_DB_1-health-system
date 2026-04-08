from flask import Blueprint


friends_bp = Blueprint("friends", __name__)

from . import routes  # noqa: E402,F401
