from flask import Blueprint

exam_reports_bp = Blueprint("exam_reports", __name__)

from . import routes  # noqa: E402,F401
