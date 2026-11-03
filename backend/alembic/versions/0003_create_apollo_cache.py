"""create apollo_cache

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "apollo_cache",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index("ix_apollo_cache_fetched_at", "apollo_cache", ["fetched_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_apollo_cache_fetched_at", table_name="apollo_cache")
    op.drop_table("apollo_cache")
