from tests.api.conftest import ALICE, BOB, SITE_ADMIN


# ---------- SUCCESS CASE ----------
def test_get_role_success(client, world, bearer, mocker):
    get_role = mocker.patch(
        "app.api.users.get_role",
        return_value=(True, False, [("admin", 1), ("manager", 2)]),
    )

    resp = client.get("/api/users/get_role", headers=bearer(**BOB))

    assert resp.status_code == 200
    # The role is looked up for the token's owner.
    assert get_role.call_args.args[1] == world["bob"]

    data = resp.get_json()
    assert data["is_manager"] is True
    assert data["is_admin"] is False
    assert data["is_site_admin"] is False
    assert data["roles"] == [
        {"role": "admin", "org_id": 1},
        {"role": "manager", "org_id": 2},
    ]


def test_get_role_from_database(client, world, bearer):
    bob = client.get("/api/users/get_role", headers=bearer(**BOB)).get_json()
    assert bob["is_admin"] is True
    assert bob["roles"] == [{"role": "admin", "org_id": world["org1"]}]

    alice = client.get("/api/users/get_role", headers=bearer(**ALICE)).get_json()
    assert (alice["is_admin"], alice["is_manager"], alice["roles"]) == (
        False,
        False,
        [],
    )


def test_get_role_reports_site_admin(client, world, bearer):
    resp = client.get("/api/users/get_role", headers=bearer(**SITE_ADMIN))
    assert resp.get_json()["is_site_admin"] is True


# ---------- NO TOKEN ----------
def test_get_role_requires_a_token(client, world):
    resp = client.get(
        "/api/users/get_role", headers={"Clerk-User-Id": "clerk_test_123"}
    )
    assert resp.status_code == 401


# ---------- INTERNAL ERROR ----------
def test_get_role_internal_error(client, world, bearer, mocker):
    mocker.patch("app.api.users.get_role", side_effect=Exception("DB exploded"))

    resp = client.get("/api/users/get_role", headers=bearer(**ALICE))

    assert resp.status_code == 500
    assert "DB exploded" in resp.get_json()["error"]
