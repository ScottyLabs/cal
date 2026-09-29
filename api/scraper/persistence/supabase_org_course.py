from scraper.persistence.supabase_writer import chunked


def upsert_orgs(db, orgs: dict) -> dict:
    """
    Upserts organizations and returns a mapping:
        {(course_num, semester): org_id}
    """
    data = []

    for org in orgs.values():
        clean = dict(org)
        clean.pop("id", None)  # Remove id if present
        clean.pop("created_at", None)
        data.append(clean)

    # Upsert: insert or update on conflict. The upsert returns the stored rows,
    # so take the IDs from it. Looking them up again with a name filter broke
    # on titles containing double quotes, which PostgREST's in.() list parses
    # as delimiters (e.g. 79-355 Fake News: "Truth" in ...).
    name_to_id = {}
    for batch in chunked(data, 200):
        res = db.table("organizations").upsert(batch, on_conflict="name").execute()
        for row in res.data:
            name_to_id[row["name"]] = row["id"]

    missing = [o["name"] for o in data if o["name"] not in name_to_id]
    if missing:
        raise RuntimeError(
            f"Organization upsert returned no row for {len(missing)} names,"
            f" e.g. {missing[0]!r}"
        )

    return {key: name_to_id[org["name"]] for key, org in orgs.items()}


def upsert_courses(db, courses: dict, org_id_by_key: dict):
    """
    Upserts courses and appends semester if it already exists.
    """

    course_numbers = [c["course_number"] for c in courses.values()]

    # Fetch existing courses
    existing_by_number = {}
    for batch in chunked(course_numbers, 200):
        res = (
            db.table("courses")
            .select("id, course_number, semesters")
            .in_("course_number", batch)
            .execute()
            .data
        )
        for row in res:
            existing_by_number[row["course_number"]] = row

    # Merge semesters
    rows_to_upsert = []

    for (course_num, semester), course in courses.items():
        org_id = org_id_by_key[(course_num, semester)]

        if course_num in existing_by_number:
            existing_semesters = existing_by_number[course_num]["semesters"] or []
            merged_semesters = sorted(set(existing_semesters + course["semesters"]))
        else:
            merged_semesters = course["semesters"]

        rows_to_upsert.append(
            {
                "course_number": course_num,
                "course_name": course["course_name"],
                "semesters": merged_semesters,
                "org_id": org_id,
            }
        )

    # Upsert merged result. Chunked: one request with every course in the
    # catalogue (~2500 rows) is slow and can hit the statement timeout.
    for batch in chunked(rows_to_upsert, 500):
        db.table("courses").upsert(batch, on_conflict="course_number").execute()
