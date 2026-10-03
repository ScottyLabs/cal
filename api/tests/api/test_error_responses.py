"""Bad ids are routing 404s, and 500 bodies do not carry exception text."""

import pytest

from tests.api.conftest import BOB


@pytest.mark.parametrize("path", ["/api/events/abc", "/api/events/abc/tags"])
def test_non_numeric_event_id_is_404(client, world, bearer, mocker, path):
    lookup = mocker.patch("app.api.events.get_event_by_id")
    tags = mocker.patch("app.api.events.get_tags_by_event")

    resp = client.get(path, headers=bearer(**BOB))

    assert resp.status_code == 404
    lookup.assert_not_called()
    tags.assert_not_called()


def test_500_body_hides_exception_text(client, world, bearer, mocker):
    mocker.patch(
        "app.api.events.get_event_by_id",
        side_effect=Exception('relation "events" does not exist'),
    )

    resp = client.get(f"/api/events/{world['ev1']}", headers=bearer(**BOB))

    assert resp.status_code == 500
    assert resp.get_json() == {"error": "Internal server error"}
    assert "relation" not in resp.get_data(as_text=True)
