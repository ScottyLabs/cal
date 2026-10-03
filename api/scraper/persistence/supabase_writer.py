# scraper/persistence/supabase_writer.py
import logging
import os

from supabase import Client, create_client

_supabase: Client | None = None

# The Supabase client logs every HTTP request (full URL, including long id
# lists) at INFO, which buries the scraper's own progress output.
logging.getLogger("httpx").setLevel(logging.WARNING)


def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        print(f"[Supabase] Connecting to {url}")
        print(f"[Supabase] Using 'SERVICE ROLE' key: {'SET' if key else 'MISSING'}")

        if not url or not key:
            raise RuntimeError(
                "Supabase env vars not set. "
                "Did you forget to call load_env() at process startup?"
            )

        _supabase = create_client(url, key)

    return _supabase


def chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]
