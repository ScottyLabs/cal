import datetime
import re
from typing import Optional, Tuple

# Month/day only; check against https://www.cmu.edu/hub/calendar/ each year.
SEMESTER_CONFIG = {
    "Spring": {
        "layout": "sched_layout_spring",
        "start": (1, 12),
        "end": (5, 5),
    },
    "Summer1": {
        "layout": "sched_layout_summer_1",
        "start": (5, 11),
        "end": (6, 18),
    },
    "Summer2": {
        "layout": "sched_layout_summer_2",
        "start": (6, 22),
        "end": (7, 31),
    },
    # 2026-27: classes Aug 24 to Dec 4 (finals do not follow the schedule).
    "Fall": {
        "layout": "sched_layout_fall",
        "start": (8, 24),
        "end": (12, 4),
    },
}


_LABEL_RE = re.compile(r"^(Spring|Summer1|Summer2|Fall)_(\d{2})$")
_HEADER_RE = re.compile(r"Semester:\s*([A-Za-z ]+?)\s+(\d{4})", re.IGNORECASE)


def get_current_semester(
    semester_label: str,
) -> Tuple[str, str, datetime.datetime, datetime.datetime]:
    """
    Resolve a semester label like 'Spring_26' into:
        (soc_layout, semester_label, semester_start, semester_end)
    """

    m = _LABEL_RE.match(semester_label or "")
    if not m:
        raise ValueError(
            f"Invalid semester label '{semester_label}'. Expected one of "
            f"{list(SEMESTER_CONFIG.keys())} plus a two-digit year, like 'Fall_26'"
        )
    name, year_suffix = m.group(1), m.group(2)
    year = 2000 + int(year_suffix)

    config = SEMESTER_CONFIG[name]

    return (
        config["layout"],
        semester_label,
        datetime.datetime(year, *config["start"]),
        datetime.datetime(year, *config["end"]),
    )


def infer_semester_label(today: Optional[datetime.date] = None) -> str:
    """
    Pick the regular semester in session on `today`: January-May is Spring,
    August-December is Fall. Summer is ambiguous (two sessions, and Fall
    registration is already open), so it must be passed explicitly.
    """
    today = today or datetime.date.today()
    yy = f"{today.year % 100:02d}"
    if 1 <= today.month <= 5:
        return f"Spring_{yy}"
    if 8 <= today.month <= 12:
        return f"Fall_{yy}"
    raise ValueError(
        f"Cannot infer the semester for {today}; pass one explicitly, "
        "e.g. --semester Summer1_26 or --semester Fall_26"
    )


def soc_header_semester(html: str) -> Optional[Tuple[str, int]]:
    """Return (term name, year) from the 'Semester: Fall 2026' page header."""
    m = _HEADER_RE.search(html[:4000])
    if not m:
        return None
    return m.group(1).strip(), int(m.group(2))


def _norm_term(name: str) -> str:
    # "Fall" -> "fall"; "Summer One" / "Summer 1" / "Summer1" -> "summer1".
    n = re.sub(r"[^a-z0-9]", "", name.lower())
    return n.replace("one", "1").replace("two", "2")


def check_soc_page_matches(html: str, semester_label: str) -> None:
    """The layout URLs are reused every year, so refuse a page for another term."""
    name, year_suffix = semester_label.split("_")
    expected = (_norm_term(name), 2000 + int(year_suffix))
    found = soc_header_semester(html)
    if found is None:
        raise RuntimeError(
            "Could not find the 'Semester:' header on the SOC page; "
            "the page format may have changed"
        )
    if (_norm_term(found[0]), found[1]) != expected:
        raise RuntimeError(
            f"SOC page is for {found[0]} {found[1]}, but the scrape was asked "
            f"for {semester_label}. Refusing to write mislabeled data."
        )
