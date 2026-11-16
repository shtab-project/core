"""Plugin registry.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str = "0002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "plugins",
        sa.Column("id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("backend_entrypoint", sa.String(500), nullable=False),
        sa.Column("frontend", sa.JSON(none_as_null=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("plugins")
