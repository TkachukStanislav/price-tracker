"""create price_history

Revision ID: e5b8a1c3d7f9
Revises: c7d2f4a8e1b3
Create Date: 2026-09-29 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5b8a1c3d7f9"
down_revision: str | None = "c7d2f4a8e1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("tracked_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_price_history_item_id_checked_at",
        "price_history",
        ["item_id", "checked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_price_history_item_id_checked_at", table_name="price_history")
    op.drop_table("price_history")
