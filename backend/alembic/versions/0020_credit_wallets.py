"""one-time credit wallet per user, replacing the daily Apollo allowance

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-11 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: Union[str, Sequence[str], None]= "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SIGNUP_CREDITS = 50
SIGNUP_GRANT = "signup"
RUN_BUDGET = 25


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "credit_wallets",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("balance", sa.Integer(), server_default="0", nullable=False),
        sa.Column("granted", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("balance >= 0", name="ck_credit_wallets_balance"),
    )
    op.create_table(
        "credit_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "reason", name="uq_credit_grants_user_reason"),
    )
    op.execute(
        sa.text(
            "INSERT INTO credit_wallets (user_id, balance, granted) "
            f"SELECT id, {SIGNUP_CREDITS}, {SIGNUP_CREDITS} FROM users"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO credit_grants (user_id, amount, reason) "
            f"SELECT id, {SIGNUP_CREDITS}, '{SIGNUP_GRANT}' FROM users"
        )
    )

    op.drop_table("apollo_usage")

    op.drop_constraint("ck_hunt_settings_daily_credit_budget", "hunt_settings", type_="check")
    op.alter_column(
        "hunt_settings",
        "daily_credit_budget",
        new_column_name="run_credit_budget",
        server_default=str(RUN_BUDGET),
    )
    op.execute(
        sa.text(
            f"UPDATE hunt_settings SET run_credit_budget = LEAST(run_credit_budget, {RUN_BUDGET})"
        )
    )
    op.create_check_constraint(
        "ck_hunt_settings_run_credit_budget", "hunt_settings", "run_credit_budget >= 0"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_hunt_settings_run_credit_budget", "hunt_settings", type_="check")
    op.alter_column(
        "hunt_settings",
        "run_credit_budget",
        new_column_name="daily_credit_budget",
        server_default="90",
    )
    op.create_check_constraint(
        "ck_hunt_settings_daily_credit_budget", "hunt_settings", "daily_credit_budget >= 0"
    )

    op.create_table(
        "apollo_usage",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("day", sa.Date()),
        sa.Column("credits", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("user_id", "day"),
    )

    op.drop_table("credit_grants")
    op.drop_table("credit_wallets")
