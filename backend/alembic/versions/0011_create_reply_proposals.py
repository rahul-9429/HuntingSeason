"""create reply_proposals

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "reply_proposals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("email_event_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_contact_id", sa.Integer(), nullable=True),
        sa.Column("sent_email_id", sa.Integer(), nullable=True),
        sa.Column(
            "cc", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column(
            "bcc", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("auto_send_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("send_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["email_event_id"], ["email_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_contact_id"], ["user_contacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sent_email_id"], ["sent_emails.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email_event_id"),
    )
    op.create_index("ix_reply_proposals_user_id_status", "reply_proposals", ["user_id", "status"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_reply_proposals_user_id_status", table_name="reply_proposals")
    op.drop_table("reply_proposals")
