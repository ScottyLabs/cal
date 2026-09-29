import pytest

from scraper.persistence.supabase_org_course import upsert_orgs


class _Result:
    def __init__(self, data):
        self.data = data


class _Table:
    """Minimal stand-in for a supabase table that echoes upserted rows."""

    def __init__(self, drop=None):
        self._drop = drop or set()
        self._next_id = 1
        self._pending = []

    def upsert(self, rows, on_conflict=None):
        self._pending = rows
        return self

    def execute(self):
        out = []
        for row in self._pending:
            if row["name"] in self._drop:
                continue
            out.append({**row, "id": self._next_id})
            self._next_id += 1
        return _Result(out)


class _DB:
    def __init__(self, table):
        self._table = table

    def table(self, name):
        assert name == "organizations"
        return self._table


def test_titles_with_double_quotes_map_to_ids():
    orgs = {
        ("79355", "Fall_26"): {
            "name": '79-355 Fake News: "Truth" in the History of American Journalism'
        },
        ("15122", "Fall_26"): {"name": "15-122 Principles of Imperative Computation"},
    }
    result = upsert_orgs(_DB(_Table()), orgs)
    assert set(result) == set(orgs)
    assert len(set(result.values())) == 2


def test_missing_row_fails_loudly():
    orgs = {
        ("15122", "Fall_26"): {"name": "15-122 Principles of Imperative Computation"}
    }
    table = _Table(drop={"15-122 Principles of Imperative Computation"})
    with pytest.raises(RuntimeError, match="returned no row"):
        upsert_orgs(_DB(table), orgs)
