"""rename middleman -> escrow (tables, enum type) + add users.total_escrow_fees

Renames the middleman_deals/middleman_messages tables to escrow_deals/
escrow_messages, renames the Postgres enum type middlemanstatus -> escrowstatus,
and splits the escrow-fee portion out of users.total_donated into a dedicated
users.total_escrow_fees column (back-filled from existing non-refunded deals).

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-06-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Stored enum values are the member NAMES (uppercase), per SQLAlchemy's default
# Enum behaviour — confirmed against the users.role column.
_FEE_PAID_STATUSES = ("FUNDED", "DELIVERED", "COMPLETED", "DISPUTED")


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    is_pg = bind.dialect.name == "postgresql"
    tables = set(insp.get_table_names())

    # 1. Rename tables (messages first is irrelevant for rename, but keep order).
    if "middleman_deals" in tables and "escrow_deals" not in tables:
        op.rename_table("middleman_deals", "escrow_deals")
    if "middleman_messages" in tables and "escrow_messages" not in tables:
        op.rename_table("middleman_messages", "escrow_messages")

    # 2. Rename the Postgres enum type (SQLite stores enums as plain strings).
    if is_pg:
        op.execute(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'middlemanstatus') "
            "AND NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'escrowstatus') "
            "THEN ALTER TYPE middlemanstatus RENAME TO escrowstatus; END IF; "
            "END $$;"
        )

    # 3. Add the total_escrow_fees column.
    user_cols = {c["name"] for c in insp.get_columns("users")}
    if "total_escrow_fees" not in user_cols:
        op.add_column(
            "users",
            sa.Column("total_escrow_fees", sa.Numeric(14, 2), server_default="0", nullable=True),
        )

    # 4. Back-fill: escrow fees were historically accumulated into total_donated.
    #    Move the fee portion into total_escrow_fees and subtract it back out of
    #    total_donated (which now tracks only user-to-user tips). escrow_deals is
    #    the post-rename table name.
    if "escrow_deals" in set(sa.inspect(bind).get_table_names()):
        status_list = ", ".join(f"'{s}'" for s in _FEE_PAID_STATUSES)
        op.execute(
            f"""
            UPDATE users SET total_escrow_fees = COALESCE((
                SELECT SUM(d.fee_amount) FROM escrow_deals d
                WHERE d.buyer_id = users.id AND d.status IN ({status_list})
            ), 0)
            """
        )
        # Clamp so total_donated never goes negative.
        op.execute(
            "UPDATE users SET total_donated = "
            "CASE WHEN COALESCE(total_donated,0) > COALESCE(total_escrow_fees,0) "
            "THEN total_donated - total_escrow_fees ELSE 0 END"
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    is_pg = bind.dialect.name == "postgresql"
    tables = set(insp.get_table_names())

    # Fold escrow fees back into total_donated before dropping the column.
    user_cols = {c["name"] for c in insp.get_columns("users")}
    if "total_escrow_fees" in user_cols:
        op.execute(
            "UPDATE users SET total_donated = COALESCE(total_donated,0) + COALESCE(total_escrow_fees,0)"
        )
        op.drop_column("users", "total_escrow_fees")

    if is_pg:
        op.execute(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'escrowstatus') "
            "AND NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'middlemanstatus') "
            "THEN ALTER TYPE escrowstatus RENAME TO middlemanstatus; END IF; "
            "END $$;"
        )

    if "escrow_deals" in tables and "middleman_deals" not in tables:
        op.rename_table("escrow_deals", "middleman_deals")
    if "escrow_messages" in tables and "middleman_messages" not in tables:
        op.rename_table("escrow_messages", "middleman_messages")
