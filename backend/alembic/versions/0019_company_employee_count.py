"""keep company headcount so Auto-Hunt can rank on company fit

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-10 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: Union[str, Sequence[str], None]= "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("companies", sa.Column("employee_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("companies", "employee_count")
