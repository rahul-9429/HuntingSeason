"""default to the email_agent writer and mark generated starter templates

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: Union[str, Sequence[str], None]= "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "outreach_settings", "writer", existing_type=sa.String(length=32), server_default="email_agent"
    )
    op.add_column(
        "email_templates",
        sa.Column("is_generated", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("email_templates", "is_generated")
    op.alter_column(
        "outreach_settings", "writer", existing_type=sa.String(length=32), server_default="template"
    )
