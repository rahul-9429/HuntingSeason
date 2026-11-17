"""look a contact up by the address an inbound email came from

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-17 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: Union[str, Sequence[str], None]= "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index("ix_contacts_lower_email", "contacts", [sa.text("lower(email)")])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_contacts_lower_email", table_name="contacts")
