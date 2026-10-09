from flask import Blueprint

api_bp = Blueprint("api", __name__)

from . import forecast, health, impact, live, recommendations, usage  # noqa: E402,F401
