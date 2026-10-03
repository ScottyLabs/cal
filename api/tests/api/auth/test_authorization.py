"""Who may call the data-changing and admin routes.

Every mutating route is listed here. Anonymous callers get 401 on all of them;
a signed-in user with no org role gets 403 on every org-scoped or global one.
"""

import pytest

import app.utils.auth as auth_module
from app.models.models import Admin, CalendarSource, Category, Event, Organization
from tests.api.conftest import ALICE, BOB, CAROL, SERVICE_TOKEN, SITE_ADMIN

# (method, path, json) with {placeholders} filled from the `world` ids.
MUTATING_ROUTES = [
    # events.py
    ("POST", "/api/events/create_event", {"org_id": "{org1}", "category_id": "{cat1}"}),
    (
        "POST",
        "/api/events/read_gcal_link",
        {"gcal_link": "https://x/y.ics", "org_id": "{org1}", "category_id": "{cat1}"},
    ),
    ("POST", "/api/events/create_recurrence_rule", {"event_id": "{ev1}"}),
    ("POST", "/api/events/create_single_event_occurrence", {"event_id": "{ev1}"}),
    ("POST", "/api/events/regenerate_occurrences_by_events", {"event_ids": ["{ev1}"]}),
    ("DELETE", "/api/events/batch_delete_events_by_params", {"semester": "Spring_26"}),
    ("DELETE", "/api/events/{ev1}", None),
    ("PATCH", "/api/events/{ev1}", {"updated_event": {"title": "pwned"}}),
    ("POST", "/api/events/user_saved_events", {"event_id": "{ev1}"}),
    ("DELETE", "/api/events/user_saved_events/{ev1}", {}),
    # google.py
    ("DELETE", "/api/google/unauthorize", None),
    ("POST", "/api/google/calendars/init", None),
    ("POST", "/api/google/calendar/events/bulk", {"calendarIds": []}),
    ("POST", "/api/google/calendar/events/add", {}),
    ("DELETE", "/api/google/calendar/events/{ev1}", {}),
    # organizations.py
    ("POST", "/api/organizations/create_org", {"name": "New Org"}),
    ("POST", "/api/organizations/create_category", {"org_id": "{org1}", "name": "x"}),
    ("DELETE", "/api/organizations/{org1}/categories/{cat1}", None),
    ("DELETE", "/api/organizations/{org1}/calendar-sources/{cs1}/events", None),
    (
        "POST",
        "/api/organizations/create_admin",
        {"user_id": "{alice}", "org_id": "{org1}", "role": "admin"},
    ),
    (
        "PATCH",
        "/api/organizations/update_admin",
        {"user_id": "{carol}", "org_id": "{org1}", "role": "manager"},
    ),
    (
        "DELETE",
        "/api/organizations/delete_admin",
        {"user_id": "{bob}", "org_id": "{org1}"},
    ),
    (
        "POST",
        "/api/organizations/bulk_create_admins",
        {"user_emails": "alice@andrew.cmu.edu", "organization_name": "Org One"},
    ),
    ("PATCH", "/api/organizations/{org1}/calendar_sources/{cs1}", {}),
    ("DELETE", "/api/organizations/{org1}/calendar_sources/{cs1}", None),
    ("DELETE", "/api/organizations/{org1}", None),
    # users.py
    ("POST", "/api/users/create_schedule", {"name": "x"}),
    ("DELETE", "/api/users/delete_schedule", {"schedule_id": 1}),
    ("POST", "/api/users/add_org_to_schedule", {"schedule_id": 1, "org_id": 1}),
    ("POST", "/api/users/remove_org_from_schedule", {"schedule_id": 1, "org_id": 1}),
]

# Routes that need an org role or site admin, i.e. everything above except the
# caller's own schedules, saved events and Google calendar.
PRIVILEGED_ROUTES = [
    r
    for r in MUTATING_ROUTES
    if not r[1].startswith(("/api/users/", "/api/google/"))
    and "user_saved_events" not in r[1]
] + [
    # Reads that expose other people's data or secret feed URLs.
    ("GET", "/api/organizations/get_admins_in_org?org_id={org1}", None),
    ("GET", "/api/organizations/{org1}/calendar_sources", None),
    (
        "POST",
        "/api/organizations/bulk_create_admins",
        {"user_emails": "alice@andrew.cmu.edu", "organization_name": "Brand New"},
    ),
    ("DELETE", "/api/events/batch_delete_events_by_params", {"org_id": "{org1}"}),
]


def _fill(value, world):
    if isinstance(value, str):
        return value.format(**world)
    if isinstance(value, list):
        return [_fill(v, world) for v in value]
    if isinstance(value, dict):
        return {k: _fill(v, world) for k, v in value.items()}
    return value


def _call(client, world, method, path, body, headers=None):
    return client.open(
        _fill(path, world),
        method=method,
        json=_fill(body, world) if body is not None else None,
        headers=headers or {},
    )


def _snapshot(db):
    db.expire_all()
    return {
        "orgs": db.query(Organization).count(),
        "categories": db.query(Category).count(),
        "events": sorted((e.id, e.title) for e in db.query(Event).all()),
        "sources": sorted((c.id, c.active) for c in db.query(CalendarSource).all()),
        "admins": sorted(
            (a.user_id, a.org_id, a.role, a.category_id) for a in db.query(Admin).all()
        ),
    }


@pytest.mark.parametrize("method, path, body", MUTATING_ROUTES)
def test_anonymous_gets_401(client, world, db, method, path, body):
    before = _snapshot(db)
    resp = _call(client, world, method, path, body)
    assert resp.status_code == 401, resp.get_json()
    assert _snapshot(db) == before


@pytest.mark.parametrize("method, path, body", MUTATING_ROUTES)
def test_clerk_header_and_body_ids_still_401(client, world, db, method, path, body):
    body = dict(body or {}, clerk_id="user_2abc", user_id=world["bob"])
    resp = _call(
        client, world, method, path, body, headers={"Clerk-User-Id": "user_2abc"}
    )
    assert resp.status_code == 401


@pytest.mark.parametrize("method, path, body", PRIVILEGED_ROUTES)
def test_user_without_a_role_gets_403(client, world, db, bearer, method, path, body):
    before = _snapshot(db)
    resp = _call(client, world, method, path, body, headers=bearer(**ALICE))
    assert resp.status_code == 403, (path, resp.status_code, resp.get_json())
    assert _snapshot(db) == before


def test_self_promotion_is_blocked(client, world, db, bearer):
    before = _snapshot(db)
    resp = _call(
        client,
        world,
        "POST",
        "/api/organizations/create_admin",
        {"user_id": "{alice}", "org_id": "{org1}", "role": "admin"},
        headers=bearer(**ALICE),
    )
    assert resp.status_code == 403
    assert _snapshot(db) == before


# --- Org admins act on their own org only -------------------------------------


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("DELETE", "/api/events/{ev2}", None),
        ("PATCH", "/api/events/{ev2}", {"updated_event": {"title": "x"}}),
        (
            "POST",
            "/api/organizations/create_category",
            {"org_id": "{org2}", "name": "x"},
        ),
        ("DELETE", "/api/organizations/{org2}", None),
        ("PATCH", "/api/organizations/{org2}/calendar_sources/{cs2}", {}),
        ("GET", "/api/organizations/{org2}/calendar_sources", None),
        (
            "POST",
            "/api/organizations/create_admin",
            {"user_id": "{alice}", "org_id": "{org2}", "role": "admin"},
        ),
        ("DELETE", "/api/events/batch_delete_events_by_params", {"org_id": "{org2}"}),
        (
            "DELETE",
            "/api/events/batch_delete_events_by_params",
            {"semester": "Spring_26"},
        ),
        # An org1 calendar source addressed through org2's path.
        ("DELETE", "/api/organizations/{org2}/calendar_sources/{cs1}", None),
        (
            "POST",
            "/api/events/create_event",
            {"org_id": "{org2}", "category_id": "{cat2}"},
        ),
        ("POST", "/api/organizations/create_org", {"name": "x"}),
    ],
)
def test_org_admin_cannot_reach_other_orgs(
    client, world, db, bearer, method, path, body
):
    before = _snapshot(db)
    resp = _call(client, world, method, path, body, headers=bearer(**BOB))
    assert resp.status_code in (403, 404), (path, resp.status_code)
    assert _snapshot(db) == before


def test_org_admin_can_manage_own_org(client, world, db, bearer):
    h = bearer(**BOB)
    assert (
        _call(
            client,
            world,
            "PATCH",
            "/api/events/{ev1}",
            {"updated_event": {"title": "Renamed"}},
            h,
        ).status_code
        == 200
    )
    assert (
        _call(
            client,
            world,
            "PATCH",
            "/api/organizations/{org1}/calendar_sources/{cs1}",
            {},
            h,
        ).status_code
        == 200
    )
    assert (
        _call(
            client,
            world,
            "GET",
            "/api/organizations/get_admins_in_org?org_id={org1}",
            None,
            h,
        ).status_code
        == 200
    )
    assert (
        _call(
            client,
            world,
            "POST",
            "/api/organizations/create_admin",
            {"user_id": "{alice}", "org_id": "{org1}", "role": "manager"},
            h,
        ).status_code
        == 200
    )
    assert (
        _call(client, world, "DELETE", "/api/events/{ev1}", None, h).status_code == 200
    )
    db.expire_all()
    assert db.get(Event, world["ev1"]) is None
    assert db.query(Admin).filter_by(user_id=world["alice"], org_id=world["org1"]).one()


def test_patch_cannot_move_an_event_to_another_org(client, world, db, bearer):
    resp = _call(
        client,
        world,
        "PATCH",
        "/api/events/{ev1}",
        {"updated_event": {"org_id": "{org2}", "title": "t"}},
        bearer(**BOB),
    )
    assert resp.status_code == 200
    db.expire_all()
    assert db.get(Event, world["ev1"]).org_id == world["org1"]

    resp = _call(
        client,
        world,
        "PATCH",
        "/api/events/{ev1}",
        {"updated_event": {"category_id": "{cat2}"}},
        bearer(**BOB),
    )
    assert resp.status_code == 400


# --- Category-scoped admins ---------------------------------------------------


def test_scoped_admin_limited_to_their_category(client, world, db, bearer):
    h = bearer(**CAROL)
    ok = _call(
        client,
        world,
        "PATCH",
        "/api/events/{ev1}",
        {"updated_event": {"title": "ok"}},
        h,
    )
    assert ok.status_code == 200

    before = _snapshot(db)
    for method, path, body in [
        ("PATCH", "/api/events/{ev1b}", {"updated_event": {"title": "x"}}),
        ("DELETE", "/api/events/{ev1b}", None),
        ("PATCH", "/api/events/{ev1}", {"updated_event": {"category_id": "{cat1b}"}}),
        # Org-wide actions, including widening her own scope.
        (
            "PATCH",
            "/api/organizations/update_admin",
            {
                "user_id": "{carol}",
                "org_id": "{org1}",
                "category_id": None,
                "role": "manager",
            },
        ),
        (
            "POST",
            "/api/organizations/create_category",
            {"org_id": "{org1}", "name": "x"},
        ),
        ("DELETE", "/api/organizations/{org1}", None),
        ("DELETE", "/api/events/batch_delete_events_by_params", {"org_id": "{org1}"}),
    ]:
        resp = _call(client, world, method, path, body, h)
        assert resp.status_code == 403, (path, resp.status_code)
    assert _snapshot(db) == before


# --- Site admins and the scraper ------------------------------------------------


def test_site_admin_can_run_global_actions(client, world, db, bearer):
    h = bearer(**SITE_ADMIN)
    assert (
        _call(
            client,
            world,
            "POST",
            "/api/organizations/create_org",
            {"name": "Brand New", "type": "CLUB"},
            h,
        ).status_code
        == 201
    )
    resp = _call(
        client,
        world,
        "DELETE",
        "/api/events/batch_delete_events_by_params",
        {"org_id": "{org2}"},
        h,
    )
    assert resp.status_code == 200
    db.expire_all()
    assert db.get(Event, world["ev2"]) is None


def test_group_claim_must_match_exactly(client, world, bearer):
    h = bearer(**dict(SITE_ADMIN, groups=("/projects/cal", "/projects/cal/admins-x")))
    resp = _call(
        client, world, "POST", "/api/organizations/create_org", {"name": "x"}, h
    )
    assert resp.status_code == 403


def test_scraper_token_only_opens_regeneration(client, world, mocker):
    regen = mocker.patch(
        "app.api.events.regenerate_event_occurrences_by_event_ids",
        return_value=([world["ev1"]], []),
    )
    service = {"Authorization": f"Bearer {SERVICE_TOKEN}"}
    resp = _call(
        client,
        world,
        "POST",
        "/api/events/regenerate_occurrences_by_events",
        {"event_ids": ["{ev1}"]},
        service,
    )
    assert resp.status_code == 201
    regen.assert_called_once()

    for method, path, body in MUTATING_ROUTES:
        if path.endswith("regenerate_occurrences_by_events"):
            continue
        resp = _call(client, world, method, path, body, service)
        assert resp.status_code == 403, (path, resp.status_code)


def test_wrong_scraper_token_is_401(client, world):
    resp = _call(
        client,
        world,
        "POST",
        "/api/events/regenerate_occurrences_by_events",
        {"event_ids": [1]},
        {"Authorization": "Bearer " + "t" * 48},
    )
    assert resp.status_code == 401


def test_scraper_token_is_compared_in_constant_time(client, world, mocker):
    compare = mocker.spy(auth_module.hmac, "compare_digest")
    resp = _call(
        client,
        world,
        "POST",
        "/api/events/regenerate_occurrences_by_events",
        {"event_ids": [1]},
        {"Authorization": "Bearer " + "t" * 48},
    )
    assert resp.status_code == 401
    compare.assert_called_once_with(("t" * 48).encode(), SERVICE_TOKEN.encode())
