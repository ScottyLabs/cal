"""Identity comes only from a verified token.

Headers, query parameters and JSON fields that name a user (the Clerk-era
`Clerk-User-Id`, `user_id` and `clerk_id`) play no part in who the caller is.
"""

import pytest

from app.models.models import Schedule, UserSavedEvent
from tests.api.conftest import ALICE, BOB


def test_health_is_public(client):
    assert client.get("/api/health").status_code == 200


@pytest.mark.parametrize(
    "method, path",
    [
        ("GET", "/api/users/me"),
        ("GET", "/api/users/get_user_id"),
        ("GET", "/api/users/get_role"),
        ("GET", "/api/users/get_admin_categories"),
        ("GET", "/api/users/schedules"),
        ("GET", "/api/schedule/"),
        ("POST", "/api/google/calendars/init"),
        ("GET", "/api/organizations/get_user_role_in_org?org_id=1"),
    ],
)
def test_clerk_user_id_header_grants_nothing(client, world, method, path):
    resp = client.open(path, method=method, headers={"Clerk-User-Id": "user_2abc"})
    assert resp.status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/api/events/user_saved_events?user_id={bob}",
        "/api/events/user_saved_event_occurrences?user_id={bob}",
        "/api/users/schedules?user_id={bob}",
    ],
)
def test_user_id_query_param_grants_nothing_anonymously(client, world, path):
    assert client.get(path.format(**world)).status_code == 401


@pytest.mark.parametrize(
    "header", ["Basic Ym9iOmh1bnRlcjI=", "Bearer", "Bearer   ", "sub-bob"]
)
def test_malformed_authorization_header(client, world, header):
    resp = client.get("/api/users/me", headers={"Authorization": header})
    assert resp.status_code == 401


def test_invalid_token_is_rejected_even_on_public_routes(client, world):
    resp = client.get("/api/events/", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


def test_me_returns_the_token_owner(client, world, bearer):
    resp = client.get("/api/users/me", headers=bearer(**BOB))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["id"] == world["bob"]
    assert body["email"] == "bob@andrew.cmu.edu"
    assert "clerk_id" not in body


def test_query_user_id_is_ignored(client, world, bearer, db):
    db.add(
        UserSavedEvent(
            user_id=world["bob"], event_id=world["ev1"], google_event_id="g1"
        )
    )
    db.commit()

    # Alice asks for Bob's saved events by id and gets her own (none).
    resp = client.get(
        f"/api/events/user_saved_events?user_id={world['bob']}", headers=bearer(**ALICE)
    )
    assert resp.status_code == 200
    assert resp.get_json() == []

    resp = client.get("/api/events/user_saved_events", headers=bearer(**BOB))
    assert resp.get_json() == [world["ev1"]]


def test_body_user_id_is_ignored_when_saving(client, world, bearer, db):
    resp = client.post(
        "/api/events/user_saved_events",
        json={"user_id": world["bob"], "event_id": world["ev1"], "google_event_id": 1},
        headers=bearer(**ALICE),
    )
    assert resp.status_code == 200
    rows = db.query(UserSavedEvent).all()
    assert [(r.user_id, r.event_id) for r in rows] == [(world["alice"], world["ev1"])]


def test_body_user_id_is_ignored_when_creating_a_schedule(client, world, bearer, db):
    resp = client.post(
        "/api/users/create_schedule",
        json={"user_id": world["bob"], "name": "Mine"},
        headers=bearer(**ALICE),
    )
    assert resp.status_code == 201
    assert resp.get_json()["user_id"] == world["alice"]
    assert db.query(Schedule).one().user_id == world["alice"]


def test_cannot_touch_someone_elses_schedule(client, world, bearer, db):
    bobs = Schedule(user_id=world["bob"], name="Bob's")
    db.add(bobs)
    db.commit()
    sid = bobs.id

    for method, path, body in [
        ("DELETE", "/api/users/delete_schedule", {"schedule_id": sid}),
        ("POST", "/api/users/add_org_to_schedule", {"schedule_id": sid, "org_id": 1}),
        (
            "POST",
            "/api/users/remove_org_from_schedule",
            {"schedule_id": sid, "org_id": 1},
        ),
    ]:
        resp = client.open(path, method=method, json=body, headers=bearer(**ALICE))
        assert resp.status_code == 404, path
    db.expire_all()
    assert db.get(Schedule, sid) is not None

    resp = client.get(f"/api/schedule/?schedule_id={sid}", headers=bearer(**ALICE))
    assert resp.status_code == 200
    assert resp.get_json().get("schedule_id") != sid


def test_event_browsing_is_public_and_personalised_when_signed_in(
    client, world, bearer, db
):
    db.add(
        UserSavedEvent(
            user_id=world["alice"], event_id=world["ev1"], google_event_id="g1"
        )
    )
    db.commit()

    anon = client.get("/api/events/")
    assert anon.status_code == 200
    assert not any(e["user_saved"] for e in anon.get_json())

    signed_in = client.get("/api/events/", headers=bearer(**ALICE))
    saved = {e["id"] for e in signed_in.get_json() if e["user_saved"]}
    assert saved == {world["ev1"]}


def test_event_detail_admin_flag_comes_from_the_token(client, world, bearer):
    path = f"/api/events/{world['ev1']}?user_id={world['bob']}"
    assert client.get(path).get_json()["user_is_admin"] is False
    assert (
        client.get(path, headers=bearer(**ALICE)).get_json()["user_is_admin"] is False
    )
    assert client.get(path, headers=bearer(**BOB)).get_json()["user_is_admin"] is True
