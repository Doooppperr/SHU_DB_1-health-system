from flask import Blueprint


ai_bp = Blueprint("ai", __name__)


from . import routes  # noqa: E402,F401
