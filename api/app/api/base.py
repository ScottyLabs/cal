import logging

from flask import Blueprint, g, jsonify
from sqlalchemy import text

from app.utils.auth import public

log = logging.getLogger(__name__)

base_bp = Blueprint("base", __name__)


@base_bp.route("/api/health", methods=["GET"])
@public
def health():
    # Kennel polls this every 2s for up to 60s after starting the service and
    # will not route the public domain here until it returns 200. Keep it off
    # the database so a slow Supabase connection can't fail the deploy -
    # /test_db below is the liveness check that does touch the DB.
    return jsonify({"status": "ok"}), 200


@base_bp.route("/")
@public
def home():
    return "Welcome to the CMUCal Flask API!"


# Public: the Supabase keepalive workflow polls it anonymously.
@base_bp.route("/test_db", methods=["GET"])
@public
def db_health_check():
    db = g.db
    try:
        db.execute(text("SELECT 1"))
        return jsonify({"status": "connected"})
    except Exception:
        log.exception("db_health_check failed")
        return jsonify({"status": "error"}), 500
