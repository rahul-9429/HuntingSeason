"""contacts from tavily

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ux_contacts_tavily_linkedin",
        "contacts",
        ["linkedin_url"],
        unique=True,
        postgresql_where=sa.text("source = 'tavily'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ux_contacts_tavily_linkedin", table_name="contacts")
    op.execute("DELETE FROM contacts WHERE source = 'tavily'")
