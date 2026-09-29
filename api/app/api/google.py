# routes requests and coordinates services/models
from flask import Blueprint, current_app, g, jsonify, redirect, request, session

from app.models.google_event import (
    delete_google_event_by_local_id,
    get_google_event_by_local_id,
    save_google_event,
)
from app.models.user import update_user_calendar_id
from app.services.google_service import (
    add_event,
    create_cmucal_calendar,
    create_google_flow,
    credentials_to_dict,
    delete_event,
    fetch_events_for_calendars,
    fetch_user_credentials,
    list_user_calendars,
    revoke_user_google_credentials,
)
from app.utils.auth import current_user, public
from app.utils.date import convert_to_iso8601

google_bp = Blueprint("google", __name__)


def _safe_redirect(url):
    """Only send the browser back to one of our own frontends (CORS allowlist)."""
    fallback = current_app.config["FRONTEND_REDIRECT_URI"]
    if not url:
        return fallback
    allowed = current_app.config.get("CORS_ORIGINS", [])
    if any(url == o or url.startswith(o.rstrip("/") + "/") for o in allowed):
        return url
    return fallback


# /authorize and /oauth/callback are top-level browser navigations (to and from
# Google), which cannot carry a bearer token. They touch only the Flask session
# cookie holding Google credentials, never a CMUCal user.
@google_bp.route("/authorize")
@public
def authorize():
    session.pop("credentials", None)
    session.pop("oauth_code_verifier", None)
    redirect_url = _safe_redirect(request.args.get("redirect"))
    print("---authorize redirect URL:", redirect_url)
    flow = create_google_flow(current_app.config)
    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    session["state"] = state
    # PKCE: token exchange must send the same verifier used in authorization_url (new Flow on callback).
    if flow.code_verifier:
        session["oauth_code_verifier"] = flow.code_verifier
    session["post_auth_redirect"] = redirect_url
    return redirect(authorization_url)


@google_bp.route("/unauthorize", methods=["DELETE", "OPTIONS"])
def unauthorize_google():
    # your logic to revoke credentials, e.g.:
    try:
        revoke_user_google_credentials()
        return jsonify({"message": "Google account unauthorized"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@google_bp.route("/oauth/callback")
@public
def oauth2callback():
    state = session["state"]
    code_verifier = session.pop("oauth_code_verifier", None)
    flow = create_google_flow(
        current_app.config, state=state, code_verifier=code_verifier
    )
    print("---oauth2callback redirect URL:", request.url)
    flow.fetch_token(authorization_response=request.url)
    session["credentials"] = credentials_to_dict(flow.credentials)
    print(
        "---oauth2callback frontend_redirect:",
        current_app.config["FRONTEND_REDIRECT_URI"],
    )
    return redirect(
        session.pop("post_auth_redirect", current_app.config["FRONTEND_REDIRECT_URI"])
    )


@google_bp.route("/calendar/status")
def calendar_status():
    return jsonify({"authorized": "credentials" in session})


@google_bp.route("/calendars/init", methods=["POST"])
def ensure_calendar():
    db = g.db
    try:
        user = current_user()
        creds = fetch_user_credentials()
        if not creds:
            return jsonify({"error": "Unauthorized"}), 401
        created = False
        if not user.calendar_id:
            calendar_id = create_cmucal_calendar(creds)
            update_user_calendar_id(user, calendar_id)
            created = True
            print("-> Created calendar for user:", calendar_id)
            db.commit()
        return jsonify({"calendar_id": user.calendar_id, "created": created}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@google_bp.route("/calendars", methods=["GET"])
def list_calendars():
    creds = fetch_user_credentials()
    if not creds:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(list_user_calendars(creds))


@google_bp.route("/calendar/events/bulk", methods=["POST"])
def bulk_events():
    creds = fetch_user_credentials()
    if not creds:
        return jsonify({"error": "Unauthorized"}), 401
    calendar_ids = request.get_json().get("calendarIds", [])
    return jsonify(fetch_events_for_calendars(creds, calendar_ids))


@google_bp.route("/calendar/events/add", methods=["POST"])
def add_event_route():
    db = g.db
    try:
        creds = fetch_user_credentials()
        if not creds:
            return jsonify({"error": "Unauthorized"}), 401

        data = request.get_json()

        user = current_user()
        if not user.calendar_id:
            return jsonify({"error": "User or calendar not found"}), 400

        calendar_id = user.calendar_id
        data["start"] = convert_to_iso8601(data["start"])  # data["start"].isoformat()
        data["end"] = convert_to_iso8601(data["end"])  # data["end"].isoformat()

        event = add_event(creds, data, calendar_id)

        ## double check that the event was not already saved, otherwise would cause duplicates
        # existing = db.query(UserSavedEvent or SyncedEvent).filter_by(
        #         user_id=user_id,
        #         google_event_id=google_event_id
        #     ).first()

        save_google_event(
            db=db,
            user_id=user.id,
            local_event_id=data["local_event_id"],
            google_event_id=event["id"],
            title=data["title"],
            start=data["start"],
            end=data["end"],
        )

        db.commit()

        return jsonify({"googleEventId": event["id"]})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@google_bp.route("/calendar/events/<local_event_id>", methods=["DELETE"])
def delete_event_route(local_event_id):
    db = g.db
    try:
        creds = fetch_user_credentials()
        if not creds:
            return jsonify({"error": "Unauthorized"}), 401

        user = current_user()
        if not user.calendar_id:
            return jsonify({"error": "User or calendar not found"}), 400

        record = get_google_event_by_local_id(db, user.id, local_event_id)
        if not record:
            return jsonify({"error": "No matching event found"}), 404

        calendar_id = user.calendar_id

        delete_event(creds, record.google_event_id, calendar_id)
        delete_google_event_by_local_id(db, user.id, local_event_id)
        db.commit()

        return jsonify({"status": "deleted"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
