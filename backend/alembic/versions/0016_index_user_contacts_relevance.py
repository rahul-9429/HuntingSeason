"""index user_contacts for relevance paging

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-07 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: Union[str, Sequence[str], None]= "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_user_contacts_user_id_relevance",
        "user_contacts",
        [
            sa.text("user_id"),
            sa.text("relevance DESC"),
            sa.text("found_at DESC"),
            sa.text("id"),
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_user_contacts_user_id_relevance", table_name="user_contacts")
