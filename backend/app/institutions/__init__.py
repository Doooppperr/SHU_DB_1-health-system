from flask import Blueprint


institutions_bp = Blueprint("institutions", __name__)

from . import routes  # noqa: E402,F401
