"""create emailed_addresses

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: Union[str, Sequence[str], None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "emailed_addresses",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column(
            "first_emailed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "email"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("emailed_addresses")
