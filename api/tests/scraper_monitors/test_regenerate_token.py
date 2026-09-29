import pytest

from scraper.scripts import export_soc


class _Response:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body or {}
        self.text = str(self._body)

    def json(self):
        return self._body


def _capture(monkeypatch, status_code=201):
    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers or {}})
        return _Response(
            status_code,
            {"regenerated_events": len(json["event_ids"]), "skipped_events": 0},
        )

    monkeypatch.setattr(export_soc.requests, "post", fake_post)
    return calls


def test_sends_bearer_token_when_set(monkeypatch):
    monkeypatch.setenv("SCRAPER_API_TOKEN", "t" * 48)
    calls = _capture(monkeypatch)

    failed = export_soc.regenerate_occurrences("https://api.example", [1, 2, 3])

    assert failed == []
    assert calls[0]["url"] == (
        "https://api.example/api/events/regenerate_occurrences_by_events"
    )
    assert calls[0]["headers"]["Authorization"] == "Bearer " + "t" * 48


def test_sends_no_token_when_unset(monkeypatch):
    monkeypatch.delenv("SCRAPER_API_TOKEN", raising=False)
    calls = _capture(monkeypatch)

    assert export_soc.regenerate_occurrences("https://api.example", [1]) == []
    assert "Authorization" not in calls[0]["headers"]


def test_rejected_token_stops_the_run(monkeypatch):
    monkeypatch.delenv("SCRAPER_API_TOKEN", raising=False)
    calls = _capture(monkeypatch, status_code=401)

    with pytest.raises(PermissionError, match="SCRAPER_API_TOKEN"):
        export_soc.regenerate_occurrences(
            "https://api.example", list(range(export_soc.REGENERATE_BATCH * 3))
        )
    assert len(calls) == 1  # stopped at the first batch, not every batch
