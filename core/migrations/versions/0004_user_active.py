"""Disable users without deleting them.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str = "0003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_active")
