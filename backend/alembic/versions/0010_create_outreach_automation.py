"""outreach state on user_contacts; email_templates, outreach_settings, daily_send_usage

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, Sequence[str], None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "user_contacts", sa.Column("stage_changed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "user_contacts",
        sa.Column("ai_stops_outreach", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "user_contacts",
        sa.Column("follow_up_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "user_contacts", sa.Column("first_contacted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "user_contacts", sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "user_contacts", sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index("ix_user_contacts_user_id_stage", "user_contacts", ["user_id", "stage"])

    op.create_table(
        "email_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("signature_html", sa.Text(), nullable=True),
        sa.Column("sender_name", sa.Text(), nullable=True),
        sa.Column("skip_ai", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_templates_user_id", "email_templates", ["user_id"])
    op.create_index(
        "ux_email_templates_one_default",
        "email_templates",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    op.create_foreign_key(
        "sent_emails_template_id_fkey",
        "sent_emails",
        "email_templates",
        ["template_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "outreach_settings",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("writer", sa.String(length=32), server_default="template", nullable=False),
        sa.Column("writer_instructions", sa.Text(), nullable=True),
        sa.Column("max_follow_ups", sa.Integer(), server_default="2", nullable=False),
        sa.Column("follow_up_interval_days", sa.Integer(), server_default="3", nullable=False),
        sa.Column("sender_name", sa.Text(), nullable=True),
        sa.Column("signature_html", sa.Text(), nullable=True),
        sa.Column("auto_send_replies", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("reply_booking_link", sa.Text(), nullable=True),
        sa.Column("reply_facts", sa.Text(), nullable=True),
        sa.Column(
            "reply_cc", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column(
            "reply_bcc", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("max_follow_ups BETWEEN 0 AND 5", name="ck_outreach_settings_max_follow_ups"),
        sa.CheckConstraint(
            "follow_up_interval_days >= 0", name="ck_outreach_settings_follow_up_interval_days"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "daily_send_usage",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("sends", sa.Integer(), server_default="0", nullable=False),
        sa.Column("follow_up_sends", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "usage_date"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("daily_send_usage")
    op.drop_table("outreach_settings")
    op.drop_constraint("sent_emails_template_id_fkey", "sent_emails", type_="foreignkey")
    op.drop_index("ux_email_templates_one_default", table_name="email_templates")
    op.drop_index("ix_email_templates_user_id", table_name="email_templates")
    op.drop_table("email_templates")
    op.drop_index("ix_user_contacts_user_id_stage", table_name="user_contacts")
    for column in (
        "replied_at",
        "last_contacted_at",
        "first_contacted_at",
        "follow_up_count",
        "ai_stops_outreach",
        "stage_changed_at",
    ):
        op.drop_column("user_contacts", column)
