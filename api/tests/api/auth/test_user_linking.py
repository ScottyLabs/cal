"""First Keycloak login links an existing users row by email, or creates one."""

import pytest

from app.models.models import Admin, User


def _me(client, bearer, **claims):
    return client.get("/api/users/me", headers=bearer(**claims))


def test_links_existing_clerk_user_by_email(client, db, bearer, user_factory):
    old = user_factory(email="Dana@andrew.cmu.edu", clerk_id="user_2clerk", fname=None)
    db.commit()

    resp = _me(
        client, bearer, sub="kc-dana", email="dana@andrew.cmu.edu", given_name="Dana"
    )
    assert resp.status_code == 200
    assert resp.get_json()["id"] == old.id

    db.expire_all()
    row = db.get(User, old.id)
    assert row.oidc_sub == "kc-dana"
    assert row.clerk_id == "user_2clerk"  # legacy data is kept
    assert row.fname == "Dana"
    assert db.query(User).count() == 1

    # Later logins find the row by sub alone, even if the email changed.
    again = _me(client, bearer, sub="kc-dana", email="renamed@andrew.cmu.edu")
    assert again.get_json()["id"] == old.id


def test_links_bulk_created_admin_placeholder(
    client, db, bearer, user_factory, org_factory
):
    org = org_factory(name="Club")
    placeholder = user_factory(email="erin@andrew.cmu.edu")
    db.add(Admin(user_id=placeholder.id, org_id=org.id, role="admin"))
    db.commit()

    resp = client.get(
        "/api/users/get_role",
        headers=bearer(sub="kc-erin", email="erin@andrew.cmu.edu"),
    )
    assert resp.status_code == 200
    assert resp.get_json()["is_admin"] is True


def test_creates_a_new_user(client, db, bearer):
    resp = _me(
        client, bearer, sub="kc-new", email="newbie@andrew.cmu.edu", given_name="New"
    )
    assert resp.status_code == 200
    user = db.query(User).one()
    assert (user.oidc_sub, user.email, user.fname) == (
        "kc-new",
        "newbie@andrew.cmu.edu",
        "New",
    )


def test_never_steals_a_row_linked_to_another_account(client, db, bearer, user_factory):
    user_factory(email="gina@andrew.cmu.edu", oidc_sub="kc-gina")
    db.commit()
    resp = _me(client, bearer, sub="kc-impostor", email="gina@andrew.cmu.edu")
    assert resp.status_code == 409
    db.expire_all()
    assert db.query(User).filter_by(oidc_sub="kc-impostor").count() == 0


@pytest.mark.parametrize("username", ["jdoe", "jdoe@andrew.cmu.edu"])
def test_links_a_real_realm_token_with_an_unverified_cmu_email(
    client, db, bearer, user_factory, username
):
    # The shape of an actual scottylabs-realm access token: CMU logins carry
    # the LDAP address (often a first.last@cmu.edu alias), email_verified is
    # false, and preferred_username is the bare Andrew ID. Every account is
    # created by the CMU login (other providers are link-only) and users cannot
    # edit username or email, so this must link the Clerk-era row.
    row = user_factory(email="jdoe@andrew.cmu.edu", clerk_id="user_2clerk")
    db.commit()
    resp = _me(
        client,
        bearer,
        sub="kc-jdoe",
        email="jane.doe@cmu.edu",
        email_verified=False,
        preferred_username=username,
    )
    assert resp.status_code == 200
    assert resp.get_json()["id"] == row.id
    db.expire_all()
    assert db.get(User, row.id).oidc_sub == "kc-jdoe"
    assert db.query(User).count() == 1


def test_non_cmu_email_is_never_used_to_link(client, db, bearer, user_factory):
    row = user_factory(email="hank@gmail.com")
    db.commit()
    for verified in (True, False):
        resp = _me(
            client,
            bearer,
            sub="kc-hank",
            email="hank@gmail.com",
            email_verified=verified,
            preferred_username="hank",
        )
        assert resp.status_code == 200
        assert resp.get_json()["id"] != row.id
    db.expire_all()
    assert db.get(User, row.id).oidc_sub is None


def test_creates_a_user_from_the_andrew_id_alone(client, db, bearer):
    resp = _me(client, bearer, sub="kc-yara", email=None, preferred_username="yara")
    assert resp.status_code == 200
    assert db.query(User).one().email == "yara@andrew.cmu.edu"


def test_no_cmu_identity_fails_private_routes_but_not_public_ones(client, db, bearer):
    claims = dict(
        sub="kc-nobody",
        email="nobody@gmail.com",
        preferred_username="not an andrew id",
    )
    assert _me(client, bearer, **claims).status_code == 403
    # A public route must still work rather than blanking the whole app.
    assert client.get("/api/events/", headers=bearer(**claims)).status_code == 200
    assert db.query(User).count() == 0
