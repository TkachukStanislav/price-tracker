"""add price_checked_at to tracked_items

Revision ID: c7d2f4a8e1b3
Revises: a3c1e5f7b9d2
Create Date: 2026-09-29 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d2f4a8e1b3"
down_revision: str | None = "a3c1e5f7b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tracked_items",
        sa.Column("price_checked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tracked_items", "price_checked_at")
