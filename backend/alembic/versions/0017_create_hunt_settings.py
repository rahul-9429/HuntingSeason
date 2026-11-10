"""create hunt_settings

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-08 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: Union[str, Sequence[str], None]= "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "hunt_settings",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("page", sa.Integer(), server_default="1", nullable=False),
        sa.Column("filters_key", sa.Text(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("companies_added", sa.Integer(), server_default="0", nullable=False),
        sa.Column("contacts_found", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("page >= 1", name="ck_hunt_settings_page"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("hunt_settings")
