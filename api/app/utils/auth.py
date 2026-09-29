"""Request authentication against ScottyLabs Keycloak.

Identity comes from exactly one place: a Keycloak access token sent as
`Authorization: Bearer <token>`. The token's signature is checked against the
realm JWKS, and its issuer, expiry and authorized party (`azp`, the OIDC
client) are checked before any claim is trusted. Nothing the client sends in a
header, query string or body is ever used to decide who the caller is.

`authenticate_request` runs as a before_request hook on every request. Routes
are protected by default; a route opts out with `@public`, and on a public
route a valid token is still honoured so the response can be personalised.

The first time a Keycloak account is seen it is linked to an existing users
row by email (users that signed in with Clerk, or were pre-created by
bulk_create_admins), otherwise a new row is created. See `resolve_user`.

Machine callers (the SOC scraper) cannot log in, so a route may additionally
accept a shared service token with `@accepts_service_token`. The token is
SCRAPER_API_TOKEN from OpenBao, sent as `Authorization: Bearer <token>`. It
identifies no user, and every other route rejects it with 403.
"""

from __future__ import annotations

import hmac
import logging
import os
import re
from functools import wraps
from typing import Optional

import jwt
from flask import current_app, g, jsonify, request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.models.models import Admin, User

log = logging.getLogger(__name__)

# Keycloak signs access tokens with the realm's RS256 key. Pinning the
# algorithm list keeps `alg: none` and HMAC key-confusion tokens out.
ALGORITHMS = ["RS256"]
LEEWAY_SECONDS = 30

CMU_EMAIL_DOMAINS = ("andrew.cmu.edu", "cmu.edu")
ANDREW_DOMAIN = "andrew.cmu.edu"
# The realm username of a CMU login is the Andrew ID (the localpart of the CMU
# UPN, same as LDAP uid).
_ANDREW_ID = re.compile(r"^[a-z0-9]+$")

SERVICE_TOKEN_ENV = "SCRAPER_API_TOKEN"
SERVICE_TOKEN_MIN_LENGTH = 32


class AuthError(Exception):
    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.message = message
        self.status = status


class TokenVerifier:
    def __init__(self, issuer: str, client_id: str, admin_group: Optional[str] = None):
        self.issuer = issuer
        self.client_id = client_id
        self.admin_group = admin_group
        # Caches the realm's signing keys and refetches when Keycloak rotates.
        # Cloudflare in front of idp.scottylabs.org rejects urllib's default
        # User-Agent with 403, so send our own.
        self.jwks = jwt.PyJWKClient(
            f"{issuer}/protocol/openid-connect/certs",
            cache_keys=True,
            lifespan=3600,
            timeout=5,
            headers={"User-Agent": "cmucal-api/1.0"},
        )

    @classmethod
    def from_env(cls, env) -> "TokenVerifier":
        url, realm, client_id = (
            (env.get(name) or "").strip()
            for name in ("KEYCLOAK_URL", "KEYCLOAK_REALM", "OIDC_CLIENT_ID")
        )
        if not (url and realm and client_id):
            raise RuntimeError(
                "Keycloak auth is not configured; set KEYCLOAK_URL, "
                "KEYCLOAK_REALM and OIDC_CLIENT_ID"
            )
        return cls(
            f"{url.rstrip('/')}/realms/{realm}",
            client_id,
            (env.get("PROJECT_ADMIN_GROUP") or "").strip() or None,
        )

    def verify(self, token: str) -> dict:
        try:
            key = self.jwks.get_signing_key_from_jwt(token).key
        except jwt.PyJWKClientConnectionError:
            raise AuthError("Unable to verify tokens right now", status=503)
        except jwt.PyJWTError as e:
            raise AuthError(f"Invalid token: {e}")
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=ALGORITHMS,
                issuer=self.issuer,
                leeway=LEEWAY_SECONDS,
                options={
                    "require": ["exp", "iat", "iss", "sub"],
                    # Keycloak access tokens name the resource server (usually
                    # "account") in aud and the client in azp; checked below.
                    "verify_aud": False,
                },
            )
        except jwt.ExpiredSignatureError:
            raise AuthError("Token expired")
        except jwt.PyJWTError as e:
            raise AuthError(f"Invalid token: {e}")

        aud = claims.get("aud")
        audiences = [aud] if isinstance(aud, str) else list(aud or [])
        if claims.get("azp") != self.client_id and self.client_id not in audiences:
            raise AuthError("Token was not issued to this client")
        # ID and refresh tokens are signed by the same realm; only accept
        # access tokens as bearer credentials.
        if claims.get("typ", "Bearer") != "Bearer":
            raise AuthError("Not an access token")
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            raise AuthError("Token has no subject")
        return claims


def _claim_str(claims: dict, name: str) -> Optional[str]:
    value = claims.get(name)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _is_cmu_email(email: str) -> bool:
    return email.rsplit("@", 1)[-1] in CMU_EMAIL_DOMAINS


def _andrew_id(claims: dict) -> Optional[str]:
    """The Andrew ID from preferred_username, bare or as an @andrew.cmu.edu UPN."""
    username = (_claim_str(claims, "preferred_username") or "").lower()
    if "@" in username:
        local, domain = username.rsplit("@", 1)
        return local if domain == ANDREW_DOMAIN and _ANDREW_ID.match(local) else None
    return username if _ANDREW_ID.match(username) else None


def _linkable_emails(claims: dict) -> list[str]:
    """Emails this token may claim an existing users row by, most specific first.

    Every account in the scottylabs realm is created by the CMU login: the
    other identity providers (cmu-dev, slack, google, cmu-saml) are link-only,
    the CMU provider only admits @andrew.cmu.edu principals and auto-links
    CMU's LDAP directory, and users cannot edit their username or email. So
    preferred_username is the Andrew ID and `email` is CMU's directory address.
    Keycloak leaves email_verified false for these accounts, so it is not
    consulted; like the other ScottyLabs services, identity rests on the realm.

    The directory address can be an alias (first.last@cmu.edu) while
    Clerk-era rows and bulk_create_admins placeholders use the Andrew UPN, so
    both are offered. Only CMU addresses are ever used to link.
    """
    emails = []
    email = (_claim_str(claims, "email") or "").lower()
    if email and "@" in email and _is_cmu_email(email):
        emails.append(email)
    andrew_id = _andrew_id(claims)
    if andrew_id:
        upn = f"{andrew_id}@{ANDREW_DOMAIN}"
        if upn not in emails:
            emails.append(upn)
    return emails


def resolve_user(db, claims: dict) -> User:
    """Map verified claims to a users row, linking or creating it on first sight."""
    sub = claims["sub"]
    user = db.query(User).filter(User.oidc_sub == sub).one_or_none()
    if user is not None:
        return user

    emails = _linkable_emails(claims)
    if not emails:
        raise AuthError("Your account has no CMU identity to sign in with", status=403)

    candidates = (
        db.query(User)
        .filter(func.lower(func.trim(User.email)).in_(emails))
        .order_by(User.created_at.asc(), User.id.asc())
        .all()
    )
    # Prefer the claimed email over the username fallback, then the oldest row
    # (the same row get_user_by_email and bulk_create_admins would pick).
    candidates.sort(key=lambda u: emails.index((u.email or "").strip().lower()))
    unlinked = [u for u in candidates if u.oidc_sub is None]

    if unlinked:
        user = unlinked[0]
        user.oidc_sub = sub
        user.fname = user.fname or _claim_str(claims, "given_name")
        user.lname = user.lname or _claim_str(claims, "family_name")
        log.info("Linked users.id=%s to a Keycloak account on first login", user.id)
    elif candidates:
        # Every row with this email already belongs to another Keycloak
        # account. Refuse rather than guess; this needs a human to look at it.
        log.warning(
            "Keycloak login for an email already linked to another account "
            "(users.id=%s)",
            candidates[0].id,
        )
        raise AuthError("This email is already linked to another account", status=409)
    else:
        user = User(
            email=emails[0],
            fname=_claim_str(claims, "given_name"),
            lname=_claim_str(claims, "family_name"),
            oidc_sub=sub,
        )
        log.info("Created a user for a new Keycloak account")

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent first request for the same account won the race.
        db.rollback()
        user = db.query(User).filter(User.oidc_sub == sub).one_or_none()
        if user is None:
            raise
    return user


def public(view):
    """Allow a route to be called without a token."""
    view._auth_public = True
    return view


def accepts_service_token(view):
    """Also accept SCRAPER_API_TOKEN on this route (g.service is set, g.user is None)."""
    view._auth_service = True
    return view


def _is_service_token(token: str) -> bool:
    expected = current_app.extensions.get("service_token")
    if not expected:
        return False
    return hmac.compare_digest(token.encode(), expected.encode())


def _bearer_token() -> Optional[str]:
    header = request.headers.get("Authorization")
    if header is None:
        return None
    scheme, _, token = header.strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthError("Authorization header must be 'Bearer <token>'")
    return token.strip()


def _auth_error_response(err: AuthError):
    resp = jsonify({"error": err.message})
    resp.status_code = err.status
    if err.status == 401:
        resp.headers["WWW-Authenticate"] = 'Bearer error="invalid_token"'
    return resp


def authenticate_request():
    g.user = None
    g.claims = None
    g.is_site_admin = False
    g.service = None

    # CORS preflights carry no credentials by design.
    if request.method == "OPTIONS":
        return None
    view = (
        current_app.view_functions.get(request.endpoint) if request.endpoint else None
    )
    if view is None:
        return None  # let Flask produce its 404/405

    try:
        token = _bearer_token()
        if token is None:
            if getattr(view, "_auth_public", False):
                return None
            raise AuthError("Authentication required")

        if _is_service_token(token):
            if not getattr(view, "_auth_service", False):
                raise AuthError("Service token is not accepted here", status=403)
            g.service = "scraper"
            return None

        verifier: TokenVerifier = current_app.extensions["token_verifier"]
        # An invalid or expired token is still a 401, even on public routes:
        # that is the web client's cue to refresh and retry.
        claims = verifier.verify(token)
        try:
            g.user = resolve_user(g.db, claims)
        except AuthError as err:
            # A valid token that maps to no user must not blank the whole app:
            # public routes fall back to the anonymous view.
            if getattr(view, "_auth_public", False):
                log.warning("Serving public route anonymously: %s", err)
                g.user = None
                return None
            raise
        g.claims = claims
        admin_group = verifier.admin_group
        groups = claims.get("groups") or []
        g.is_site_admin = bool(admin_group) and admin_group in groups
    except AuthError as err:
        return _auth_error_response(err)
    return None


def init_auth(app, verifier: Optional[TokenVerifier] = None, env=None) -> None:
    env = os.environ if env is None else env
    if verifier is None:
        verifier = TokenVerifier.from_env(env)
    service_token = (env.get(SERVICE_TOKEN_ENV) or "").strip()
    if service_token and len(service_token) < SERVICE_TOKEN_MIN_LENGTH:
        raise RuntimeError(
            f"{SERVICE_TOKEN_ENV} must be at least {SERVICE_TOKEN_MIN_LENGTH} characters"
        )
    app.extensions["token_verifier"] = verifier
    app.extensions["service_token"] = service_token or None
    app.before_request(authenticate_request)


def current_user() -> Optional[User]:
    return g.get("user")


def forbidden(message: str = "You do not have permission to do that"):
    return jsonify({"error": message}), 403


def is_site_admin() -> bool:
    """Member of PROJECT_ADMIN_GROUP (ScottyLabs cal admins) in Keycloak."""
    return bool(g.get("is_site_admin"))


def site_admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_site_admin():
            return forbidden("Only CMUCal site admins can do that")
        return view(*args, **kwargs)

    return wrapper


def site_admin_or_service_required(view):
    """For routes marked @accepts_service_token: site admins or the scraper."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if not (g.get("service") or is_site_admin()):
            return forbidden("Only CMUCal site admins can do that")
        return view(*args, **kwargs)

    return wrapper


def org_admin_record(db, org_id) -> Optional[Admin]:
    user = current_user()
    if user is None or org_id is None:
        return None
    try:
        org_id = int(org_id)
    except (TypeError, ValueError):
        return None
    return (
        db.query(Admin).filter(Admin.org_id == org_id, Admin.user_id == user.id).first()
    )


ORG_ROLES = ("admin", "manager")


def is_org_member(db, org_id) -> bool:
    """Site admin, or holds any admin/manager row in the org."""
    if is_site_admin():
        return True
    admin = org_admin_record(db, org_id)
    return admin is not None and admin.role in ORG_ROLES


def can_manage_org(db, org_id) -> bool:
    """Org-wide control: its admins, categories, and deleting it.

    Site admin, or an admin/manager of the org whose scope is not narrowed to
    one category. A category-scoped admin cannot manage other admins, which
    would otherwise let them widen their own scope.
    """
    if is_site_admin():
        return True
    admin = org_admin_record(db, org_id)
    return admin is not None and admin.role in ORG_ROLES and admin.category_id is None


def can_edit_category(db, org_id, category_id) -> bool:
    """Events and iCal sources in one category of an org.

    Site admin, an org-wide admin/manager, or one scoped to this category.
    This matches the manager dashboard, where `category_id: null` means the
    whole org.
    """
    if is_site_admin():
        return True
    admin = org_admin_record(db, org_id)
    if admin is None or admin.role not in ORG_ROLES:
        return False
    if admin.category_id is None:
        return True
    try:
        return category_id is not None and int(category_id) == admin.category_id
    except (TypeError, ValueError):
        return False
