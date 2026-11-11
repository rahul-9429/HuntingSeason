"""hold automated outreach to the recipient's local business hours

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-11 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: Union[str, Sequence[str], None]= "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "outreach_settings",
        sa.Column(
            "email_send_schedule_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=True,
        ),
    )
    op.add_column(
        "outreach_settings",
        sa.Column(
            "email_send_schedule",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("outreach_settings", "email_send_schedule")
    op.drop_column("outreach_settings", "email_send_schedule_enabled")
