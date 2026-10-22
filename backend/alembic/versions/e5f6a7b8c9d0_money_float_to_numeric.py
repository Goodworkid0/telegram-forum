"""convert USD money columns from float to Numeric(14,2)

Postgres: ALTER each USD column to numeric(14,2), rounding existing values to
cents. SQLite (dev): values are dynamically typed and SQLAlchemy now reads them
as Decimal, so we just round in place to clean float artifacts (no type change).

Crypto pay/payout amounts and percentage config stay float.

Revision ID: e5f6a7b8c9d0
Revises: d3e4f5a6b7c8
Create Date: 2026-06-21

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, [usd money columns])
MONEY_COLUMNS = {
    "users": ["balance", "pending_balance", "total_donated", "total_received", "referral_earnings"],
    "badges": ["price", "reward_balance"],
    "crypto_deposits": ["price_amount", "price_amount_usd"],
    "withdrawal_requests": ["amount", "fee_amount", "net_amount"],
    "ledger_entries": ["amount", "balance_after"],
    "donations": ["amount"],
    "middleman_deals": ["amount", "fee_amount"],
    "app_settings": ["min_deposit_amount", "min_withdrawal_amount", "min_donation_amount"],
    "daily_reward_config": ["balance_amount"],
}


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    for table, cols in MONEY_COLUMNS.items():
        for col in cols:
            if is_pg:
                op.execute(
                    f"ALTER TABLE {table} ALTER COLUMN {col} TYPE numeric(14,2) "
                    f"USING round({col}::numeric, 2)"
                )
            else:
                # SQLite: round in place; SQLAlchemy's Numeric reads it as Decimal.
                op.execute(f"UPDATE {table} SET {col} = round({col}, 2) WHERE {col} IS NOT NULL")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table, cols in MONEY_COLUMNS.items():
        for col in cols:
            op.execute(
                f"ALTER TABLE {table} ALTER COLUMN {col} TYPE double precision "
                f"USING {col}::double precision"
            )
