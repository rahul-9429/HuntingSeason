"""space automated sends out instead of sending them in one burst

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-17 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: Union[str, Sequence[str], None]= "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "outreach_settings",
        sa.Column("min_gap_seconds", sa.Integer(), server_default="180", nullable=False),
    )
    op.add_column(
        "outreach_settings",
        sa.Column("max_gap_seconds", sa.Integer(), server_default="900", nullable=False),
    )
    op.add_column(
        "mailboxes",
        sa.Column("next_send_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("mailboxes", "next_send_at")
    op.drop_column("outreach_settings", "max_gap_seconds")
    op.drop_column("outreach_settings", "min_gap_seconds")
