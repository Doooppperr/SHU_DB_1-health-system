from flask import Blueprint

appointments_bp = Blueprint("appointments", __name__)

from . import routes  # noqa: E402,F401
