# course_agent/app/db/supabase_client.py
import os

from supabase import create_client

_supabase = None


def get_supabase():
    global _supabase
    if _supabase is None:
        _supabase = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )
    return _supabase
