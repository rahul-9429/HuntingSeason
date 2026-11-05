"""create email_events; link sent_emails to user_contacts

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("sent_emails", "contact_id", new_column_name="user_contact_id")
    op.alter_column("sent_emails", "company_id", new_column_name="user_company_id")
    op.create_foreign_key(
        "sent_emails_user_contact_id_fkey",
        "sent_emails",
        "user_contacts",
        ["user_contact_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "sent_emails_user_company_id_fkey",
        "sent_emails",
        "user_companies",
        ["user_company_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_sent_emails_user_contact_id", "sent_emails", ["user_contact_id"])

    op.create_table(
        "email_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("mailbox_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_message_id", sa.Text(), nullable=False),
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("from_address", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("internet_message_id", sa.Text(), nullable=True),
        sa.Column(
            "to_addresses",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "cc_addresses",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("sent_email_id", sa.Integer(), nullable=True),
        sa.Column("user_contact_id", sa.Integer(), nullable=True),
        sa.Column("classification_label", sa.String(length=32), nullable=True),
        sa.Column("classification_reason", sa.Text(), nullable=True),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mailbox_id"], ["mailboxes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sent_email_id"], ["sent_emails.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_contact_id"], ["user_contacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_message_id"),
    )
    op.create_index("ix_email_events_user_id", "email_events", ["user_id"])
    op.create_index("ix_email_events_user_contact_id", "email_events", ["user_contact_id"])
    op.create_index(
        "ix_email_events_mailbox_id_thread_id", "email_events", ["mailbox_id", "thread_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_email_events_mailbox_id_thread_id", table_name="email_events")
    op.drop_index("ix_email_events_user_contact_id", table_name="email_events")
    op.drop_index("ix_email_events_user_id", table_name="email_events")
    op.drop_table("email_events")
    op.drop_index("ix_sent_emails_user_contact_id", table_name="sent_emails")
    op.drop_constraint("sent_emails_user_company_id_fkey", "sent_emails", type_="foreignkey")
    op.drop_constraint("sent_emails_user_contact_id_fkey", "sent_emails", type_="foreignkey")
    op.alter_column("sent_emails", "user_company_id", new_column_name="company_id")
    op.alter_column("sent_emails", "user_contact_id", new_column_name="contact_id")
