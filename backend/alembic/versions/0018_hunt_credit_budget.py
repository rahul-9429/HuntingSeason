"""let each user cap what Auto-Hunt spends

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-09 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: Union[str, Sequence[str], None]= "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "hunt_settings",
        sa.Column("daily_credit_budget", sa.Integer(), server_default="90", nullable=False),
    )
    op.create_check_constraint(
        "ck_hunt_settings_daily_credit_budget", "hunt_settings", "daily_credit_budget >= 0"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_hunt_settings_daily_credit_budget", "hunt_settings", type_="check")
    op.drop_column("hunt_settings", "daily_credit_budget")
