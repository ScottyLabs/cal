"""Fixtures for the API tests.

Tokens are signed with an RSA key generated here and served through a fake
JWKS, so the real verification path runs end to end without Keycloak. The
database is an in-memory SQLite copy of the schema, so the real route and
permission code runs without Postgres.
"""

import json
import re
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import BigInteger, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import DefaultClause
from sqlalchemy.types import ARRAY

from app.models import Base
from app.utils.auth import TokenVerifier

KID = "test-kid"
SERVICE_TOKEN = "s" * 48


# --- SQLite stand-ins for the Postgres-only DDL ------------------------------


@compiles(BigInteger, "sqlite")
def _bigint_sqlite(type_, compiler, **kw):
    return "INTEGER"  # so BIGINT primary keys autoincrement


@compiles(JSONB, "sqlite")
def _jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


@compiles(ARRAY, "sqlite")
def _array_sqlite(type_, compiler, **kw):
    return "TEXT"


def _sqlite_metadata():
    for table in Base.metadata.tables.values():
        for col in table.columns:
            default = col.server_default
            if default is None:
                continue
            arg = str(getattr(default, "arg", ""))
            if "now()" in arg:
                col.server_default = DefaultClause(text("CURRENT_TIMESTAMP"))
            elif "::" in arg:
                col.server_default = DefaultClause(
                    text(re.sub(r"::[\w ]+(\[\])?", "", arg))
                )
    return Base.metadata


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    _sqlite_metadata().create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def db(session_factory):
    """Overrides the Postgres `db` fixture, so the shared factories use SQLite."""
    session = session_factory()
    yield session
    session.close()


# --- Keys and tokens ---------------------------------------------------------


@pytest.fixture(scope="session")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def attacker_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def jwks(rsa_key):
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(rsa_key.public_key()))
    jwk.update(kid=KID, alg="RS256", use="sig")
    return {"keys": [jwk]}


@pytest.fixture
def verifier(jwks):
    verifier = TokenVerifier(
        "https://idp.test/realms/scottylabs", "cal", "/projects/cal/admins"
    )
    verifier.jwks.fetch_data = lambda: jwks
    return verifier


@pytest.fixture
def auth_app(app, verifier, session_factory, monkeypatch):
    monkeypatch.setitem(app.extensions, "token_verifier", verifier)
    monkeypatch.setitem(app.extensions, "service_token", SERVICE_TOKEN)
    # open_db() looks get_session up in the app package at request time.
    monkeypatch.setattr("app.get_session", session_factory)
    return app


@pytest.fixture
def client(auth_app):
    return auth_app.test_client()


@pytest.fixture
def make_token(rsa_key, verifier):
    def _make(
        sub="sub-alice",
        email="alice@andrew.cmu.edu",
        groups=(),
        key=None,
        kid=KID,
        algorithm="RS256",
        **overrides,
    ):
        now = int(time.time())
        claims = {
            "iss": verifier.issuer,
            "sub": sub,
            "aud": "account",
            "azp": verifier.client_id,
            "typ": "Bearer",
            "iat": now,
            "exp": now + 300,
            "email": email,
            "email_verified": True,
            "preferred_username": email,
            "given_name": "Test",
            "family_name": "User",
            "groups": list(groups),
        }
        claims.update(overrides)
        claims = {k: v for k, v in claims.items() if v is not None}
        headers = {"kid": kid} if kid else {}
        return jwt.encode(
            claims,
            key if key is not None else rsa_key,
            algorithm=algorithm,
            headers=headers,
        )

    return _make


@pytest.fixture
def bearer(make_token):
    def _bearer(**kwargs):
        return {"Authorization": f"Bearer {make_token(**kwargs)}"}

    return _bearer


# --- A small world: two orgs, their admins, and a plain user ------------------


@pytest.fixture
def world(
    db,
    user_factory,
    org_factory,
    category_factory,
    event_factory,
    calendar_source_factory,
    admin_factory,
):
    """Seeds and commits; returns plain ids so tests never hold live ORM rows."""
    org1 = org_factory(name="Org One", type="CLUB")
    org2 = org_factory(name="Org Two", type="CLUB")
    cat1 = category_factory(org_id=org1.id, name="General")
    cat1b = category_factory(org_id=org1.id, name="Workshops")
    cat2 = category_factory(org_id=org2.id, name="Other")
    ev1 = event_factory(org=org1, category=cat1, title="One", user_edited=None)
    ev1b = event_factory(org=org1, category=cat1b, title="One B", user_edited=None)
    ev2 = event_factory(org=org2, category=cat2, title="Two", user_edited=None)
    cs1 = calendar_source_factory(org=org1, category=cat1)
    cs2 = calendar_source_factory(org=org2, category=cat2)

    # Linked users, as after their first Keycloak login.
    alice = user_factory(email="alice@andrew.cmu.edu", oidc_sub="sub-alice")
    bob = user_factory(email="bob@andrew.cmu.edu", oidc_sub="sub-bob")
    carol = user_factory(email="carol@andrew.cmu.edu", oidc_sub="sub-carol")
    admin_factory(user=bob, org=org1, role="admin")  # org-wide admin of org1
    admin_factory(user=carol, org=org1, role="admin", category_id=cat1.id)
    db.commit()

    return {
        "org1": org1.id,
        "org2": org2.id,
        "cat1": cat1.id,
        "cat1b": cat1b.id,
        "cat2": cat2.id,
        "ev1": ev1.id,
        "ev1b": ev1b.id,
        "ev2": ev2.id,
        "cs1": cs1.id,
        "cs2": cs2.id,
        "alice": alice.id,
        "bob": bob.id,
        "carol": carol.id,
    }


ALICE = {"sub": "sub-alice", "email": "alice@andrew.cmu.edu"}  # no org role
BOB = {"sub": "sub-bob", "email": "bob@andrew.cmu.edu"}  # org1 admin
CAROL = {"sub": "sub-carol", "email": "carol@andrew.cmu.edu"}  # org1 cat1 only
SITE_ADMIN = {
    "sub": "sub-root",
    "email": "root@andrew.cmu.edu",
    "groups": ("/projects/cal", "/projects/cal/admins"),
}
