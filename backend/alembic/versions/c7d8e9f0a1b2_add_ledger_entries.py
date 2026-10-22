"""add append-only ledger_entries (and seed opening balances)

Creates the ledger_entries table and seeds one 'opening_balance' row per user
for any nonzero balance / pending_balance, so the invariant
SUM(amount) == current balance holds from introduction onward.

Idempotent: skips table creation if it already exists (dev create_all) and skips
seeding users that already have an entry.

Revision ID: c7d8e9f0a1b2
Revises: f1a2b3c4d5e6
Create Date: 2026-06-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = 'ledger_entries'


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if TABLE not in insp.get_table_names():
        op.create_table(
            TABLE,
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('account', sa.String(), nullable=False, server_default='balance'),
            sa.Column('amount', sa.Float(), nullable=False),
            sa.Column('balance_after', sa.Float(), nullable=False),
            sa.Column('entry_type', sa.String(), nullable=False),
            sa.Column('ref_type', sa.String(), nullable=True),
            sa.Column('ref_id', sa.Integer(), nullable=True),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_ledger_entries_user_id', TABLE, ['user_id'])
        op.create_index('ix_ledger_entries_account', TABLE, ['account'])
        op.create_index('ix_ledger_entries_entry_type', TABLE, ['entry_type'])
        op.create_index('ix_ledger_entries_created_at', TABLE, ['created_at'])
        op.create_index('ix_ledger_user_account', TABLE, ['user_id', 'account'])
        op.create_index('ix_ledger_ref', TABLE, ['ref_type', 'ref_id'])

    # Seed opening balances (idempotent — skip users that already have an entry).
    op.execute("""
        INSERT INTO ledger_entries (user_id, account, amount, balance_after, entry_type, description, created_at)
        SELECT id, 'balance', COALESCE(balance, 0), COALESCE(balance, 0), 'opening_balance',
               'Opening balance at ledger introduction', CURRENT_TIMESTAMP
        FROM users
        WHERE COALESCE(balance, 0) <> 0
          AND NOT EXISTS (
              SELECT 1 FROM ledger_entries le
              WHERE le.user_id = users.id AND le.account = 'balance'
          )
    """)
    op.execute("""
        INSERT INTO ledger_entries (user_id, account, amount, balance_after, entry_type, description, created_at)
        SELECT id, 'pending', COALESCE(pending_balance, 0), COALESCE(pending_balance, 0), 'opening_balance',
               'Opening pending balance at ledger introduction', CURRENT_TIMESTAMP
        FROM users
        WHERE COALESCE(pending_balance, 0) <> 0
          AND NOT EXISTS (
              SELECT 1 FROM ledger_entries le
              WHERE le.user_id = users.id AND le.account = 'pending'
          )
    """)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if TABLE in insp.get_table_names():
        op.drop_table(TABLE)
