"""create mailboxes, sent_emails

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "mailboxes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("credentials", postgresql.JSONB(), nullable=False),
        sa.Column("from_name", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("gmail_history_id", sa.BigInteger(), nullable=True),
        sa.Column("gmail_watch_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outlook_subscriptions", postgresql.JSONB(), nullable=True),
        sa.Column(
            "warmup_started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        "ux_mailboxes_lower_email", "mailboxes", [sa.text("lower(email)")], unique=True
    )
    op.create_table(
        "sent_emails",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("mailbox_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_message_id", sa.Text(), nullable=False),
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("internet_message_id", sa.Text(), nullable=True),
        sa.Column("contact_id", sa.Integer(), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("writer", sa.String(length=32), nullable=True),
        sa.Column("follow_up_attempt", sa.Integer(), server_default="0", nullable=False),
        sa.Column("delivery_status", sa.String(length=32), server_default="sent", nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mailbox_id"], ["mailboxes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_message_id"),
    )
    op.create_index("ix_sent_emails_user_id", "sent_emails", ["user_id"])
    op.create_index(
        "ix_sent_emails_mailbox_id_thread_id", "sent_emails", ["mailbox_id", "thread_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_sent_emails_mailbox_id_thread_id", table_name="sent_emails")
    op.drop_index("ix_sent_emails_user_id", table_name="sent_emails")
    op.drop_table("sent_emails")
    op.drop_index("ux_mailboxes_lower_email", table_name="mailboxes")
    op.drop_table("mailboxes")
