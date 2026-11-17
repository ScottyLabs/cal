import logging

from flask import Blueprint, g, jsonify, request
from sqlalchemy import or_

from app.models.models import (
    CalendarSource,
    Category,
    Event,
    EventOccurrence,
    Schedule,
)
from app.utils.auth import current_user
from icalendar import Calendar, Event as ICalEvent


log = logging.getLogger(__name__)

schedule_bp = Blueprint("schedule_bp", __name__)


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

def find_user_schedule(db, user, schedule_id=None):
    schedule_query = db.query(Schedule).filter(Schedule.user_id == user.id)
    if schedule_id:
        schedule = schedule_query.filter(Schedule.id == schedule_id).first()
    else:
        schedule = schedule_query.first()
        
    if not schedule:
        return None
    
    return schedule
    
    
def org_occurrence(db, org, category):
    # Get events for this category (exclude events from inactive sources)
    events = (
        db.query(Event)
        .outerjoin(
            CalendarSource,
            Event.calendar_source_id == CalendarSource.id,
        )
        .filter(
            Event.org_id == org.id,
            Event.category_id == category.id,
            or_(
                Event.calendar_source_id == None,
                CalendarSource.active == True,
            ),  
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
    
    return occurrences

# get_schedule_download -> get_schedule_routebut eith a different route and everything in 
# Build a Calendar with one VEVENT per EventOccurrence (UID, DTSTART, DTEND, SUMMARY, LOCATION, DESCRIPTION). Return cal.to_ical() with mimetype="text/calendar" and Content-Disposition: attachment; filename="cmucal.ics".
@schedule_bp.route("/export", methods=["GET"])
def get_schedule_download():
    schedule_id = request.args.get("schedule_id")
    user = current_user()
    
    try:
        db = g.db
        schedule = find_user_schedule(db, user, schedule_id)
            
        if schedule is None:
            return jsonify({"error": "Schedule not found"}), 404
            
        cal = Calendar()
        for schedule_org in schedule.schedule_orgs:
            org = schedule_org.org
            # Same org types the schedule view shows
            if not org or org.type not in ("COURSE", "ACADEMIC", "CLUB"):
                continue

            categories = db.query(Category).filter(Category.org_id == org.id).all()
            for category in categories:
                for occ in org_occurrence(db, org, category):
                    vevent = ICalEvent()
                    vevent.add("uid", occ.id)
                    vevent.add("dtstart", occ.start_datetime)
                    vevent.add("dtend", occ.end_datetime)
                    vevent.add("summary", occ.title)
                    vevent.add("location", occ.location)
                    vevent.add("description", occ.description)
                    cal.add_component(vevent)
    except Exception:
        log.exception("get_schedule_download failed")
        return jsonify({"error": "Internal server error"}), 500                    
    

    return cal.to_ical(), 200, {"Content-Type": "text/calendar", "Content-Disposition": "attachment; filename=cmucal.ics"}


@schedule_bp.route("/", methods=["GET"])
def get_schedule_route():
    """returns the user's schedule with courses and clubs, their categories, and event occurrences"""
    schedule_id = request.args.get("schedule_id")
    user = current_user()

    db = g.db
    try:
        # Get specific schedule or user's first schedule
        schedule = find_user_schedule(db, user, schedule_id)
        if not schedule:
            return jsonify({"courses": [], "clubs": []})

        courses = {}
        clubs = {}

        # Get all organizations in the schedule
        for schedule_org in schedule.schedule_orgs:
            org = schedule_org.org
            if not org:
                continue

            # Get all categories for this org
            categories = db.query(Category).filter(Category.org_id == org.id).all()

            # Check if org is a course or club
            if org.type == "COURSE" or org.type == "ACADEMIC":
                courses[org.id] = {
                    "org_id": org.id,
                    "name": org.name,
                    "categories": [],
                    "events": {},
                }

                # Add categories and their events
                for category in categories:
                    courses[org.id]["categories"].append(
                        {"id": category.id, "name": category.name}
                    )

                    occurrences = org_occurrence(db, org, category)
                    courses[org.id]["events"][category.name] = [
                        event_occurrence_to_dict(o) for o in occurrences
                    ]

            elif org.type == "CLUB":
                clubs[org.id] = {
                    "org_id": org.id,
                    "name": org.name,
                    "categories": [],
                    "events": {},
                }

                # Add categories and their events
                for category in categories:
                    clubs[org.id]["categories"].append(
                        {"id": category.id, "name": category.name}
                    )

                    occurrences = org_occurrence(db, org, category)
                    clubs[org.id]["events"][category.name] = [
                        event_occurrence_to_dict(o) for o in occurrences
                    ]

        return jsonify(
            {
                "courses": list(courses.values()),
                "clubs": list(clubs.values()),
                "schedule_id": schedule.id,
            }
        )
    except Exception:
        log.exception("get_schedule_route failed")
        return jsonify({"error": "Internal server error"}), 500
