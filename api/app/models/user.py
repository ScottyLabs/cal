# app/models/user.py
from sqlalchemy import func

from app.models.models import User


def user_to_dict(user):
    return {
        "id": user.id,
        "email": user.email,
        "fname": user.fname,
        "lname": user.lname,
        "calendar_id": user.calendar_id,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def create_placeholder_user(db, email, fname=None, lname=None, **kwargs):
    """Create a user row ahead of their first login (for bulk admin setup).

    The row has no oidc_sub; the owner of the email claims it on their first
    Keycloak login (see app.utils.auth.resolve_user).
    """
    user = User(email=email, fname=fname, lname=lname, **kwargs)
    db.add(user)
    return user


def get_user_by_email(db, email: str):
    return (
        db.query(User)
        .filter(func.lower(func.trim(User.email)) == email.strip().lower())
        .order_by(User.created_at.asc(), User.id.asc())
        .first()
    )


def get_user_by_oidc_sub(db, sub: str):
    return db.query(User).filter(User.oidc_sub == sub).one_or_none()


def get_user_by_id(db, user_id: int):
    return db.query(User).filter(User.id == user_id).first()


def update_user_calendar_id(user, calendar_id):
    user.calendar_id = calendar_id
    return user
