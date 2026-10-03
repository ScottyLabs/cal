import logging
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request
from sqlalchemy import or_

from app.models.admin import (
    create_admin,
    delete_admin,
    get_admin_by_org_and_user,
    get_admins_by_org,
    update_admin,
)
from app.models.category import (
    create_category,
    delete_category,
    get_categories_by_org_id,
)
from app.models.models import (
    CalendarSource,
    Category,
    Event,
    EventOccurrence,
    Organization,
)
from app.models.organization import (
    create_organization,
    get_organization_by_id,
    get_organization_by_name,
    get_orgs_by_type,
)
from app.models.user import (
    create_placeholder_user,
    get_user_by_email,
    get_user_by_id,
)
from app.services.ical import delete_events_for_calendar_source
from app.utils.auth import (
    ORG_ROLES,
    can_edit_category,
    can_manage_org,
    current_user,
    forbidden,
    is_org_member,
    is_site_admin,
    public,
    site_admin_required,
)
from app.utils.course_data import get_course_data

log = logging.getLogger(__name__)

orgs_bp = Blueprint("orgs", __name__)


def event_occurrence_to_dict(occurrence: EventOccurrence):
    """Manually serialize EventOccurrence SQLAlchemy object to a dictionary."""
    return {
        "id": occurrence.id,
        "title": occurrence.title,
        "description": occurrence.description,
        "start_datetime": occurrence.start_datetime.isoformat(),
        "end_datetime": occurrence.end_datetime.isoformat(),
        "location": occurrence.location,
        "is_all_day": occurrence.is_all_day,
        "source_url": occurrence.source_url,
        "recurrence": occurrence.recurrence.name if occurrence.recurrence else None,
        "event_id": occurrence.event_id,
        "org_id": occurrence.org_id,
        "category_id": occurrence.category_id,
    }


@orgs_bp.route("/org/<int:org_id>", methods=["GET"])
@public
def get_organization_data(org_id):
    """returns a single organization's data with its categories and event occurrences"""
    db = g.db
    try:
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            return jsonify({"error": "Organization not found"}), 404

        org_data = {
            "org_id": org.id,
            "name": org.name,
            "type": org.type,
            "categories": [],
            "events": {},
        }

        # Get all categories for this org
        categories = db.query(Category).filter(Category.org_id == org.id).all()

        # Build set of known category IDs for the uncategorized fallback
        category_ids = [c.id for c in categories]

        # Add categories and their events
        for category in categories:
            org_data["categories"].append({"id": category.id, "name": category.name})

            # Get events for this category (exclude events from inactive sources)
            events = (
                db.query(Event)
                .outerjoin(
                    CalendarSource, Event.calendar_source_id == CalendarSource.id
                )
                .filter(
                    Event.org_id == org.id,
                    Event.category_id == category.id,
                    or_(
                        Event.calendar_source_id == None, CalendarSource.active == True
                    ),  # noqa: E711
                )
                .all()
            )

            # Get event occurrences
            event_ids = [e.id for e in events]
            occurrences = []
            if event_ids:
                occurrences = (
                    db.query(EventOccurrence)
                    .filter(EventOccurrence.event_id.in_(event_ids))
                    .all()
                )

            org_data["events"][category.name] = [
                event_occurrence_to_dict(o) for o in occurrences
            ]

        # Include events with no category (or stale category_id not in known set)
        # Exclude events from inactive calendar sources in all cases
        active_source_filter = or_(
            Event.calendar_source_id == None, CalendarSource.active == True
        )  # noqa: E711
        uncategorized_events = (
            db.query(Event)
            .outerjoin(CalendarSource, Event.calendar_source_id == CalendarSource.id)
            .filter(
                Event.org_id == org.id,
                Event.category_id == None,  # noqa: E711
                active_source_filter,
            )
            .all()
        )
        if category_ids:
            # Also grab events whose category_id was deleted
            stale_events = (
                db.query(Event)
                .outerjoin(
                    CalendarSource, Event.calendar_source_id == CalendarSource.id
                )
                .filter(
                    Event.org_id == org.id,
                    Event.category_id != None,  # noqa: E711
                    ~Event.category_id.in_(category_ids),
                    active_source_filter,
                )
                .all()
            )
            uncategorized_events = uncategorized_events + stale_events

        if uncategorized_events:
            unc_event_ids = [e.id for e in uncategorized_events]
            unc_occurrences = (
                db.query(EventOccurrence)
                .filter(EventOccurrence.event_id.in_(unc_event_ids))
                .all()
            )
            org_data["events"]["Uncategorized"] = [
                event_occurrence_to_dict(o) for o in unc_occurrences
            ]

        return jsonify(org_data)

    except Exception:
        log.exception("get_organization_data failed")
        return jsonify({"error": "Internal server error"}), 500


@orgs_bp.route("/get_all_orgs", methods=["GET"])
@public
def get_all_orgs():
    db = g.db
    try:
        orgs = db.query(Organization).all()
        orgs_list = []
        for org in orgs:
            orgs_list.append(
                {
                    "id": org.id,
                    "name": org.name,
                    "description": org.description,
                    "type": org.type,
                    "tags": org.tags,
                }
            )

        return jsonify(orgs_list), 200
    except Exception:
        log.exception("get_all_orgs failed")
        return jsonify({"error": "Internal server error"}), 500


@orgs_bp.route("/get_course_orgs", methods=["GET"])
@public
def get_course_orgs():
    db = g.db
    try:
        orgs = get_orgs_by_type(db, org_type="COURSE")
        log.debug("Found %d COURSE organizations", len(orgs))
        orgs_list = []
        for org in orgs:
            parts = org.name.split(" ")
            course_num = parts[0]
            course_title = " ".join(parts[1:])
            orgs_list.append(
                {
                    "id": org.id,
                    "number": course_num,
                    "title": course_title,
                    "label": org.name,
                }
            )

        return jsonify(orgs_list), 200
    except Exception:
        log.exception("get_course_orgs failed")
        return jsonify({"error": "Internal server error"}), 500


@orgs_bp.route("/get_club_orgs", methods=["GET"])
@public
def get_club_orgs():
    db = g.db
    try:
        orgs = get_orgs_by_type(db, org_type="CLUB")
        log.debug("Found %d CLUB organizations", len(orgs))

        if not orgs:
            # Return empty list instead of 404 for better UX
            return jsonify([]), 200

        orgs_list = []
        for org in orgs:
            orgs_list.append(
                {
                    "id": org.id,
                    "name": org.name,
                    "description": org.description,
                }
            )

        return jsonify(orgs_list), 200
    except Exception:
        log.exception("get_club_orgs failed")
        return jsonify({"error": "Internal server error"}), 500


@orgs_bp.route("/get_courses", methods=["GET"])
@public
def get_courses_from_soc():
    """
    Endpoint to fetch course data from the JSON file.
    To update the JSON file, follow the instructions in the README in the rust directory.
    """
    try:
        courses = get_course_data()
        return jsonify(courses), 200
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception:
        return jsonify({"error": "An error occurred while fetching course data."}), 500


@orgs_bp.route("/create_org", methods=["POST"])
@site_admin_required
def create_org_record():
    db = g.db
    try:
        data = request.get_json()
        org_name = data.get("name")
        org_description = data.get("description", None)
        org_type = data.get("type", None)
        if not org_name:
            return jsonify({"error": "Missing org_name"}), 400

        org = create_organization(
            db, name=org_name, description=org_description, type=org_type
        )
        db.commit()
        return jsonify({"status": "created", "org_id": org.id}), 201
    except Exception:
        log.exception("create_org_record failed")
        return jsonify({"error": "Internal server error"}), 500


@orgs_bp.route("/create_category", methods=["POST"])
def create_category_record():
    db = g.db
    try:
        data = request.get_json()
        org_id = data.get("org_id")
        if not org_id:
            return jsonify({"error": "Missing org_id"}), 400
        if not can_manage_org(db, org_id):
            return forbidden()
        name = data.get("name")
        if not name:
            return jsonify({"error": "Missing category name"}), 400

        category = create_category(db, org_id=org_id, name=name)
        db.commit()
        return jsonify({"status": "category created", "category_id": category.id}), 201
    except Exception:
        log.exception("create_category_record failed")
        return jsonify({"error": "Internal server error"}), 500


@orgs_bp.route("/<int:org_id>/categories/<int:cat_id>", methods=["DELETE"])
def delete_category_record(org_id: int, cat_id: int):
    """Delete a category. Fails if the org doesn't own it."""
    db = g.db
    if not can_manage_org(db, org_id):
        return forbidden()
    try:
        from app.models.models import Category as CategoryModel

        category = (
            db.query(CategoryModel)
            .filter(
                CategoryModel.id == cat_id,
                CategoryModel.org_id == org_id,
            )
            .first()
        )
        if not category:
            return jsonify({"error": "Category not found"}), 404
        deleted = delete_category(db, category_id=cat_id)
        if not deleted:
            return jsonify({"error": "Category not found"}), 404
        db.commit()
        return jsonify({"status": "category deleted", "category_id": cat_id}), 200
    except Exception:
        log.exception("delete_category_record failed")
        return jsonify({"error": "Internal server error"}), 500


@orgs_bp.route(
    "/<int:org_id>/calendar-sources/<int:calendar_source_id>/events", methods=["DELETE"]
)
def delete_events_and_deactivate_calendar(org_id: int, calendar_source_id: int):
    """
    Deletes all events associated with a calendar source
    and deactivates the calendar source for the given org.

    curl -X DELETE \
    http://localhost:5001/api/organizations/<org_id>/calendar-sources/<calendar_source_id>/events
    """
    db = g.db
    calendar_source = (
        db.query(CalendarSource)
        .filter(
            CalendarSource.id == calendar_source_id, CalendarSource.org_id == org_id
        )
        .one_or_none()
    )
    if not calendar_source:
        return jsonify({"error": "CalendarSource not found"}), 404
    if not can_edit_category(db, org_id, calendar_source.category_id):
        return forbidden()
    try:
        deleted_event_ids = delete_events_for_calendar_source(
            db=db,
            calendar_source_id=calendar_source_id,
        )

        db.commit()

        return jsonify(
            {
                "status": "ok",
                "org_id": org_id,
                "calendar_source_id": calendar_source_id,
                "deleted_events": len(deleted_event_ids),
                "event_ids": deleted_event_ids,
            }
        ), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    except Exception:
        log.exception("delete_events_and_deactivate_calendar failed")
        return jsonify({"error": "Internal server error"}), 500


@orgs_bp.route("/create_admin", methods=["POST"])
def create_admin_record():
    db = g.db
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        if not user_id:
            return jsonify({"error": "Missing user_id"}), 400
        org_id = data.get("org_id")
        if not org_id:
            return jsonify({"error": "Missing org_id"}), 400
        if not can_manage_org(db, org_id):
            return forbidden()
        role = data.get("role", "admin")
        if role not in ORG_ROLES:
            return jsonify({"error": f"role must be one of {list(ORG_ROLES)}"}), 400
        category_id = data.get("category_id", None)

        admin = create_admin(
            db, org_id=org_id, user_id=user_id, role=role, category_id=category_id
        )
        db.commit()
        return jsonify(
            {"status": "admin created", "user": admin.user_id, "org": admin.org_id}
        ), 200
    except Exception:
        log.exception("create_admin_record failed")
        return jsonify({"error": "Internal server error"}), 500


@orgs_bp.route("/update_admin", methods=["PATCH"])
def update_admin_record():
    """Update an admin's role and/or category assignment."""
    db = g.db
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        if not user_id:
            return jsonify({"error": "Missing user_id"}), 400
        org_id = data.get("org_id")
        if not org_id:
            return jsonify({"error": "Missing org_id"}), 400
        if not can_manage_org(db, org_id):
            return forbidden()

        role = data.get("role", None)
        if role is not None and role not in ORG_ROLES:
            return jsonify({"error": f"role must be one of {list(ORG_ROLES)}"}), 400
        category_id = data.get("category_id", None)

        admin = update_admin(
            db, org_id=org_id, user_id=user_id, role=role, category_id=category_id
        )
        if not admin:
            return jsonify({"error": "Admin not found"}), 404

        db.commit()
        return jsonify(
            {
                "status": "admin updated",
                "user": admin.user_id,
                "org": admin.org_id,
                "role": admin.role,
                "category_id": admin.category_id,
            }
        ), 200
    except Exception:
        log.exception("update_admin_record failed")
        return jsonify({"error": "Internal server error"}), 500


@orgs_bp.route("/delete_admin", methods=["DELETE"])
def delete_admin_record():
    db = g.db
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        if not user_id:
            return jsonify({"error": "Missing user_id"}), 400
        org_id = data.get("org_id")
        if not org_id:
            return jsonify({"error": "Missing org_id"}), 400
        if not can_manage_org(db, org_id):
            return forbidden()

        deleted = delete_admin(db, org_id=org_id, user_id=user_id)
        if not deleted:
            return jsonify({"error": "Admin not found"}), 404
        db.commit()
        return jsonify({"status": "admin deleted", "user": user_id, "org": org_id}), 200
    except Exception:
        log.exception("delete_admin_record failed")
        return jsonify({"error": "Internal server error"}), 500


@orgs_bp.route("/bulk_create_admins", methods=["POST"])
def bulk_create_admins():
    """
    Create multiple users and assign them as admins to organizations.

    Expected payload:
    {
        "user_emails": "email1@example.com,email2@example.com,email3@example.com",
        "organization_name": "ScottyLabs"
    }
    """
    db = g.db
    try:
        data = request.get_json()
        user_emails_str = data.get("user_emails")
        organization_name = data.get("organization_name")

        role = data.get("role", "admin")
        if role not in ORG_ROLES:
            return jsonify({"error": f"role must be one of {list(ORG_ROLES)}"}), 400

        if not user_emails_str or not organization_name:
            return jsonify({"error": "Missing user_emails or organization_name"}), 400

        # Adding admins to an existing org is an org-level action; creating the
        # org as a side effect is a global one.
        existing_org = get_organization_by_name(db, organization_name)
        if existing_org is None:
            if not is_site_admin():
                return forbidden("Only CMUCal site admins can create organizations")
        elif not can_manage_org(db, existing_org.id):
            return forbidden()

        # Parse comma-separated emails
        user_emails = [
            email.strip() for email in user_emails_str.split(",") if email.strip()
        ]

        if not user_emails:
            return jsonify({"error": "No valid emails provided"}), 400

        # Find or create organization
        organization = existing_org
        if not organization:
            # Create new organization
            organization = create_organization(db, name=organization_name, type="CLUB")

        # Get or create categories for this organization
        categories = get_categories_by_org_id(db, organization.id)
        if not categories:
            # Create default "Main" category
            main_category = create_category(db, org_id=organization.id, name="Main")
            categories = [main_category]

        created_users = []
        created_admins = []
        errors = []

        for email in user_emails:
            try:
                # Find or create user
                user = get_user_by_email(db, email)
                if not user:
                    # Placeholder row; its owner claims it on first login
                    user = create_placeholder_user(db, email=email)
                    created_users.append(user.email)

                # Check if admin relationship already exists
                existing_admin = get_admin_by_org_and_user(db, organization.id, user.id)
                if existing_admin:
                    # Update existing admin with category if needed
                    if not existing_admin.category_id and categories:
                        existing_admin.category_id = categories[0].id
                        db.add(existing_admin)
                        db.commit()
                    continue

                # Create admin relationship
                category_id = categories[0].id if categories else None
                admin = create_admin(
                    db,
                    org_id=organization.id,
                    user_id=user.id,
                    role=role,
                    category_id=category_id,
                )
                created_admins.append(
                    {
                        "user_email": user.email,
                        "user_id": user.id,
                        "org_id": organization.id,
                        "category_id": category_id,
                    }
                )

            except Exception as e:
                errors.append(f"Error processing {email}: {str(e)}")
                continue

        response_data = {
            "status": "success",
            "organization": {"id": organization.id, "name": organization.name},
            "categories": [{"id": cat.id, "name": cat.name} for cat in categories],
            "created_users": created_users,
            "created_admins": created_admins,
            "errors": errors,
        }

        db.commit()
        return jsonify(response_data), 201

    except Exception:
        log.exception("bulk_create_admins failed")
        return jsonify({"error": "Internal server error"}), 500


@orgs_bp.route("/get_admins_in_org", methods=["GET"])
def get_admins_in_org():
    db = g.db
    try:
        org_id = request.args.get("org_id")
        if not org_id:
            return jsonify({"error": "Missing org_id"}), 400
        if not is_org_member(db, org_id):
            return forbidden()

        admins = get_admins_by_org(db, org_id=int(org_id))

        admins_list = []
        for admin in admins:
            user = get_user_by_id(db, admin.user_id)
            org = get_organization_by_id(db, admin.org_id)
            andrew_id = user.email.split("@")[0] if user.email else "N/A"
            admins_list.append(
                {
                    "user_id": user.id,
                    "andrew_id": andrew_id,
                    "user_email": user.email,
                    "org_id": org.id,
                    "org_name": org.name,
                    "role": admin.role,
                    "category_id": admin.category_id,
                }
            )

        return jsonify(admins_list), 200
    except Exception:
        log.exception("get_admins_in_org failed")
        return jsonify({"error": "Internal server error"}), 500


@orgs_bp.route("/get_user_role_in_org", methods=["GET"])
def get_user_role_in_org():
    db = g.db
    try:
        user = current_user()

        org_id = request.args.get("org_id")
        if not org_id:
            return jsonify({"error": "Missing org_id"}), 400

        admin = get_admin_by_org_and_user(db, org_id=int(org_id), user_id=int(user.id))
        if not admin:
            return jsonify({"role": "member"}), 200

        return jsonify({"role": admin.role}), 200
    except Exception:
        log.exception("get_user_role_in_org failed")
        return jsonify({"error": "Internal server error"}), 500


@orgs_bp.route("/<int:org_id>/calendar_sources", methods=["GET"])
def list_calendar_sources(org_id: int):
    db = g.db
    # iCal URLs are often secret "private address" feeds.
    if not is_org_member(db, org_id):
        return forbidden()
    calendar_sources = (
        db.query(CalendarSource).filter(CalendarSource.org_id == org_id).all()
    )

    def cs_to_dict(cs):
        return {
            "id": getattr(cs, "id", None),
            "url": getattr(cs, "url", None),
            "active": getattr(cs, "active", None),
            "category_id": getattr(cs, "category_id", None),
            "notes": getattr(cs, "notes", None),
            "default_event_type": getattr(cs, "default_event_type", None),
            "created_by_user_id": getattr(cs, "created_by_user_id", None),
            "last_sync_status": getattr(cs, "last_sync_status", None),
            "last_fetched_at": getattr(cs, "last_fetched_at", None).isoformat()
            if getattr(cs, "last_fetched_at", None)
            else None,
            "created_at": getattr(cs, "created_at", None).isoformat()
            if getattr(cs, "created_at", None)
            else None,
            "updated_at": getattr(cs, "updated_at", None).isoformat()
            if getattr(cs, "updated_at", None)
            else None,
        }

    return jsonify(
        {"calendar_sources": [cs_to_dict(cs) for cs in calendar_sources]}
    ), 200


@orgs_bp.route("/<int:org_id>/calendar_sources/<int:cs_id>", methods=["PATCH"])
def toggle_calendar_source_active(org_id: int, cs_id: int):
    db = g.db
    # Acquire row lock to avoid races
    calendar_source = (
        db.query(CalendarSource)
        .filter(CalendarSource.id == cs_id, CalendarSource.org_id == org_id)
        .with_for_update()
        .one_or_none()
    )

    if not calendar_source:
        return jsonify({"error": "CalendarSource not found"}), 404
    if not can_edit_category(db, org_id, calendar_source.category_id):
        return forbidden()

    # Toggle active flag
    calendar_source.active = not bool(calendar_source.active)
    calendar_source.updated_at = datetime.now(timezone.utc)
    db.commit()

    return (
        jsonify(
            {
                "id": calendar_source.id,
                "active": calendar_source.active,
                "updated_at": calendar_source.updated_at.isoformat(),
            }
        ),
        200,
    )


@orgs_bp.route("/<int:org_id>/calendar_sources/<int:cs_id>", methods=["DELETE"])
def delete_calendar_source(org_id: int, cs_id: int):
    """Delete a CalendarSource and all its events."""
    db = g.db
    try:
        calendar_source = (
            db.query(CalendarSource)
            .filter(CalendarSource.id == cs_id, CalendarSource.org_id == org_id)
            .one_or_none()
        )
        if not calendar_source:
            return jsonify({"error": "CalendarSource not found"}), 404
        if not can_edit_category(db, org_id, calendar_source.category_id):
            return forbidden()

        # Delete all events attached to this source first
        delete_events_for_calendar_source(db=db, calendar_source_id=cs_id)

        # Now delete the CalendarSource record itself
        db.query(CalendarSource).filter(CalendarSource.id == cs_id).delete()
        db.commit()

        return jsonify({"status": "ok", "deleted_calendar_source_id": cs_id}), 200

    except Exception:
        log.exception("delete_calendar_source failed")
        return jsonify({"error": "Internal server error"}), 500


@orgs_bp.route("/<int:org_id>", methods=["DELETE"])
def delete_organization(org_id: int):
    db = g.db
    if not can_manage_org(db, org_id):
        return forbidden()
    org = db.query(Organization).filter(Organization.id == org_id).one_or_none()
    if not org:
        return jsonify({"error": "Organization not found"}), 404

    db.delete(org)
    db.commit()
    return "", 204
