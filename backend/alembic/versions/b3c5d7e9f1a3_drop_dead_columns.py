"""drop dead columns found by the 2026-07 dead-code audit

- users.rules_accepted_at: rules-acceptance feature removed (clients post their
  rules as a forum thread instead).
- users.total_donated / total_received: no donation/tip feature ever existed.
- crypto_deposits.provider: always 'nowpayments', never read.
- withdrawal_requests.payout_id / payout_status / payout_error / payout_amount:
  only ever written by the NOWPayments payout webhook, which was removed
  (payouts are approved manually; payout_hash + payout_currency stay).
- giveaway_entries.guest_key: no guest-entry flow exists.
- app_settings.min_donation_amount / support_user_id: never read.

Revision ID: b3c5d7e9f1a3
Revises: a2b4c6d8e0f2
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b3c5d7e9f1a3'
down_revision: Union[str, None] = 'a2b4c6d8e0f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.drop_column('rules_accepted_at')
        batch.drop_column('total_donated')
        batch.drop_column('total_received')
    with op.batch_alter_table('crypto_deposits') as batch:
        batch.drop_column('provider')
    with op.batch_alter_table('withdrawal_requests') as batch:
        batch.drop_column('payout_id')
        batch.drop_column('payout_status')
        batch.drop_column('payout_error')
        batch.drop_column('payout_amount')
    with op.batch_alter_table('giveaway_entries') as batch:
        batch.drop_column('guest_key')
    with op.batch_alter_table('app_settings') as batch:
        batch.drop_column('min_donation_amount')
        batch.drop_column('support_user_id')


def downgrade() -> None:
    with op.batch_alter_table('app_settings') as batch:
        batch.add_column(sa.Column('min_donation_amount', sa.Numeric(14, 2), nullable=True))
        batch.add_column(sa.Column('support_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    with op.batch_alter_table('giveaway_entries') as batch:
        batch.add_column(sa.Column('guest_key', sa.String(64), nullable=True))
    with op.batch_alter_table('withdrawal_requests') as batch:
        batch.add_column(sa.Column('payout_id', sa.String(), nullable=True))
        batch.add_column(sa.Column('payout_status', sa.String(), nullable=True))
        batch.add_column(sa.Column('payout_error', sa.Text(), nullable=True))
        batch.add_column(sa.Column('payout_amount', sa.Float(), nullable=True))
    with op.batch_alter_table('crypto_deposits') as batch:
        batch.add_column(sa.Column('provider', sa.String(), nullable=True))
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('rules_accepted_at', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('total_donated', sa.Numeric(14, 2), nullable=True))
        batch.add_column(sa.Column('total_received', sa.Numeric(14, 2), nullable=True))
