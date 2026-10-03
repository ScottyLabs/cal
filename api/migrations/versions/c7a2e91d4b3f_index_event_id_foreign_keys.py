"""index event_id on event_occurrences and recurrence_rules

Revision ID: c7a2e91d4b3f
Revises: b41f7c2d9e10
Create Date: 2026-10-02 22:00:00.000000

Neither foreign key had an index, so every cascaded delete of an event, and
every lookup of an event's occurrences or rule, scanned the whole table.
Purely additive.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c7a2e91d4b3f"
down_revision: Union[str, Sequence[str], None] = "b41f7c2d9e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("event_occurrences_event_id_idx", "event_occurrences", ["event_id"])
    op.create_index("recurrence_rules_event_id_idx", "recurrence_rules", ["event_id"])


def downgrade() -> None:
    op.drop_index("recurrence_rules_event_id_idx", table_name="recurrence_rules")
    op.drop_index("event_occurrences_event_id_idx", table_name="event_occurrences")
