"""add hnsw index on title_embedding

Revision ID: a3c1e5f7b9d2
Revises: df18c4810c4b
Create Date: 2026-09-29 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3c1e5f7b9d2"
down_revision: str | None = "df18c4810c4b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_tracked_items_title_embedding_hnsw",
        "tracked_items",
        ["title_embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"title_embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_tracked_items_title_embedding_hnsw", table_name="tracked_items")
