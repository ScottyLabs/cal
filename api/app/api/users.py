import logging

from flask import Blueprint, g, jsonify, request

from app.models.admin import get_categories_for_admin_user, get_role
from app.models.category import join_org_and_to_dict
from app.models.models import Schedule
from app.models.schedule import create_schedule, delete_schedule
from app.models.schedule_org import create_schedule_org, remove_schedule_org
from app.models.user import user_to_dict
from app.utils.auth import current_user, is_site_admin

log = logging.getLogger(__name__)

users_bp = Blueprint("users", __name__)

# Every route here acts on the caller, who is always g.user: authenticate_request
# has already verified the bearer token and rejected the request without one.


def _owned_schedule(db, schedule_id):
    """The caller's schedule with this id, or None (also for someone else's)."""
    try:
        schedule_id = int(schedule_id)
    except (TypeError, ValueError):
        return None
    return (
        db.query(Schedule)
        .filter(Schedule.id == schedule_id, Schedule.user_id == current_user().id)
        .first()
    )


@users_bp.route("/me", methods=["GET"])
def get_me():
    """The signed-in user's own record. Replaces the Clerk-era POST /login."""
    user = current_user()
    return jsonify({**user_to_dict(user), "is_site_admin": is_site_admin()}), 200


@users_bp.route("/get_user_id", methods=["GET"])
def get_user_id():
    return jsonify({"user_id": current_user().id}), 200


@users_bp.route("/create_schedule", methods=["POST"])
def create_schedule_record():
    db = g.db
    try:
        data = request.get_json(silent=True) or {}
        name = data.get("name")
        if not name:
            return jsonify({"error": "Missing name"}), 400

        user_id = current_user().id
        schedule = create_schedule(db, user_id=user_id, name=name)
        db.commit()
        return jsonify(
            {
                "status": "schedule created",
                "user_id": user_id,
                "schedule_id": schedule.id,
            }
        ), 201
    except Exception as e:
        log.exception("create_schedule_record failed")
        return jsonify({"error": str(e)}), 500


@users_bp.route("/delete_schedule", methods=["DELETE"])
def delete_schedule_record():
    db = g.db
    try:
        # Try to get data from JSON body, fallback to query args
        data = request.get_json(silent=True) or {}
        schedule_id = data.get("schedule_id") or request.args.get("schedule_id")

        if not schedule_id:
            return jsonify({"error": "Missing schedule_id"}), 400
        if _owned_schedule(db, schedule_id) is None:
            return jsonify({"error": "Schedule not found"}), 404

        success = delete_schedule(db, schedule_id=schedule_id)
        db.commit()

        if success:
            return jsonify(
                {"status": "schedule deleted", "schedule_id": schedule_id}
            ), 200
        else:
            return jsonify({"error": "Schedule not found"}), 404
    except Exception as e:
        log.exception("delete_schedule_record failed")
        return jsonify({"error": str(e)}), 500


@users_bp.route("/add_org_to_schedule", methods=["POST"])
def add_org_to_schedule():
    db = g.db
    try:
        data = request.get_json(silent=True) or {}
        schedule_id = data.get("schedule_id")
        org_id = data.get("org_id")
        if not schedule_id or not org_id:
            return jsonify({"error": "Missing schedule_id or org_id"}), 400
        if _owned_schedule(db, schedule_id) is None:
            return jsonify({"error": "Schedule not found"}), 404

        schedule_org = create_schedule_org(db, schedule_id=schedule_id, org_id=org_id)
        db.commit()
        return jsonify(
            {
                "status": "organization added to schedule",
                "schedule_id": schedule_id,
                "org_id": org_id,
            }
        ), 201
    except Exception as e:
        log.exception("add_org_to_schedule failed")
        return jsonify({"error": str(e)}), 500


@users_bp.route("/remove_org_from_schedule", methods=["POST"])
def remove_org_from_schedule():
    db = g.db
    try:
        data = request.get_json(silent=True) or {}
        schedule_id = data.get("schedule_id")
        org_id = data.get("org_id")
        if not schedule_id or not org_id:
            return jsonify({"error": "Missing schedule_id or org_id"}), 400
        if _owned_schedule(db, schedule_id) is None:
            return jsonify({"error": "Schedule not found"}), 404

        success = remove_schedule_org(db, schedule_id=schedule_id, org_id=org_id)
        db.commit()
        if success:
            return jsonify(
                {
                    "status": "organization removed from schedule",
                    "schedule_id": schedule_id,
                    "org_id": org_id,
                }
            ), 200
        else:
            return jsonify({"error": "Organization not found in schedule"}), 404
    except Exception as e:
        log.exception("remove_org_from_schedule failed")
        return jsonify({"error": str(e)}), 500


@users_bp.route("/schedules", methods=["GET"])
def get_user_schedules():
    try:
        user = current_user()

        # Convert schedules to dict format with schedule_orgs
        schedules = [
            {
                "id": schedule.id,
                "name": schedule.name,
                "schedule_orgs": [
                    {
                        "org_id": org.org_id,
                        "org_name": org.org.name if org.org else None,
                    }
                    for org in schedule.schedule_orgs
                ],
            }
            for schedule in user.schedules
        ]
        return jsonify(schedules), 200

    except Exception as e:
        log.exception("get_user_schedules failed")
        return jsonify({"error": str(e)}), 500


@users_bp.route("/get_admin_categories", methods=["GET"])
def get_admin_categories():
    db = g.db
    try:
        categories = get_categories_for_admin_user(db, current_user().id)
        results = [join_org_and_to_dict(db, category.id) for category in categories]
        return jsonify(results), 200

    except Exception as e:
        log.exception("get_admin_categories failed")
        return jsonify({"error": str(e)}), 500


@users_bp.route("/get_role", methods=["GET"])
def get_user_role():
    db = g.db
    try:
        is_manager, is_admin, role_orgs = get_role(db, current_user().id)

        return jsonify(
            {
                "is_manager": is_manager,
                "is_admin": is_admin,
                "is_site_admin": is_site_admin(),
                "roles": [
                    {"role": role, "org_id": org_id} for role, org_id in role_orgs
                ],
            }
        ), 200
    except Exception as e:
        log.exception("get_user_role failed")
        return jsonify({"error": str(e)}), 500
