from flask import Blueprint

booking_v7_bp = Blueprint("booking_v7", __name__)

from . import routes  # noqa: E402,F401
