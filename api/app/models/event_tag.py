import logging

from app.models.models import EventTag, Tag

log = logging.getLogger(__name__)


def save_event_tag(db, event_id: int, tag_id: int):
    """
    Save a tag associated with an event in the database.

    Args:
        db: Database session.
        event_id: ID of the event.
        tag_id: ID of the tag to be saved.

    Returns:
        The created EventTag object.
    """
    event_tag = EventTag(event_id=event_id, tag_id=tag_id)
    db.add(event_tag)
    return event_tag


def get_tags_by_event(db, event_id: int):
    tags = (
        db.query(Tag.id, Tag.name)
        .join(Tag.event_tags)  # relationship set up in models
        .filter(EventTag.event_id == event_id)  # filter by the event id
        .all()
    )
    return tags


def delete_event_tag(db, event_id, tag_id):
    db.query(EventTag).filter_by(event_id=event_id, tag_id=tag_id).delete()
    log.debug("Deleted event tag event_id=%s tag_id=%s", event_id, tag_id)
