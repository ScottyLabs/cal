import datetime

import pytest

from scraper.helpers.semester import (
    check_soc_page_matches,
    get_current_semester,
    infer_semester_label,
    soc_header_semester,
)

FALL_HEADER = (
    "<HTML><TITLE> Carnegie Mellon University - Full Schedule Of Classes</TITLE>"
    "<BODY><P><B>Run Date: 28-sep-2026\n<BR><B>Semester: Fall 2026</B><P>"
)


def test_fall_26_dates():
    layout, label, start, end = get_current_semester("Fall_26")
    assert layout == "sched_layout_fall"
    assert label == "Fall_26"
    assert start == datetime.datetime(2026, 8, 24)
    assert end == datetime.datetime(2026, 12, 4)


@pytest.mark.parametrize("label", ["Fall26", "Autumn_26", "Fall_2026", ""])
def test_rejects_bad_labels(label):
    with pytest.raises(ValueError):
        get_current_semester(label)


@pytest.mark.parametrize(
    "today, expected",
    [
        (datetime.date(2026, 1, 5), "Spring_26"),
        (datetime.date(2026, 5, 31), "Spring_26"),
        (datetime.date(2026, 8, 1), "Fall_26"),
        (datetime.date(2026, 9, 28), "Fall_26"),
        (datetime.date(2026, 12, 31), "Fall_26"),
    ],
)
def test_infer_semester_label(today, expected):
    assert infer_semester_label(today) == expected


def test_infer_refuses_summer():
    with pytest.raises(ValueError):
        infer_semester_label(datetime.date(2026, 7, 1))


def test_header_parsing():
    assert soc_header_semester(FALL_HEADER) == ("Fall", 2026)
    assert soc_header_semester("<html>nothing here</html>") is None


def test_page_must_match_label():
    check_soc_page_matches(FALL_HEADER, "Fall_26")
    with pytest.raises(RuntimeError):
        check_soc_page_matches(FALL_HEADER, "Fall_27")
    with pytest.raises(RuntimeError):
        check_soc_page_matches(FALL_HEADER.replace("Fall", "Spring"), "Fall_26")
    with pytest.raises(RuntimeError):
        check_soc_page_matches("<html></html>", "Fall_26")
