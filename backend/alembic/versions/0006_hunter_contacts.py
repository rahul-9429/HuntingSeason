"""contacts from hunter

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "contacts", sa.Column("source", sa.Text(), server_default="apollo", nullable=False)
    )
    op.add_column("contacts", sa.Column("email_source", sa.Text(), nullable=True))
    op.execute("UPDATE contacts SET email_source = 'apollo' WHERE email IS NOT NULL")
    op.alter_column("contacts", "apollo_person_id", existing_type=sa.Text(), nullable=True)
    op.create_index(
        "ux_contacts_hunter_email",
        "contacts",
        ["email"],
        unique=True,
        postgresql_where=sa.text("source = 'hunter'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ux_contacts_hunter_email", table_name="contacts")
    op.execute("DELETE FROM contacts WHERE apollo_person_id IS NULL")
    op.alter_column("contacts", "apollo_person_id", existing_type=sa.Text(), nullable=False)
    op.drop_column("contacts", "email_source")
    op.drop_column("contacts", "source")
