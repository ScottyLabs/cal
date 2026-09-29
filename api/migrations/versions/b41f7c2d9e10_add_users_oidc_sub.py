"""add users.oidc_sub for Keycloak logins

Revision ID: b41f7c2d9e10
Revises: 55da73f9050c
Create Date: 2026-09-28 18:45:00.000000

Purely additive, so it is safe to apply before the code that uses it deploys:
the running (Clerk-era) code maps only the columns it knows about and ignores
the new one. users.clerk_id is kept untouched; nothing is dropped.

oidc_sub holds the Keycloak `sub` claim. It is NULL for every existing row
until that user's first Keycloak login links it (see app/utils/auth.py).
Postgres allows any number of NULLs under a unique constraint.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b41f7c2d9e10"
# 55da73f9050c ("add agent_run to events") is where the prod and dev databases
# are.
down_revision: Union[str, Sequence[str], None] = "55da73f9050c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("oidc_sub", sa.Text(), nullable=True))
    op.create_unique_constraint("users_oidc_sub_key", "users", ["oidc_sub"])


def downgrade() -> None:
    op.drop_constraint("users_oidc_sub_key", "users", type_="unique")
    op.drop_column("users", "oidc_sub")
