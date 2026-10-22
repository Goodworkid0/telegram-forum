"""add_trialmode_and_shop_prices

Admin-configurable: trial_mode_enabled (off => new users get USER role) and the
shop prices (premium, membership, name change, thread title, thread auto-bump).

Revision ID: a7b9c1d3e5f7
Revises: e5f7a9b1c3d5
Create Date: 2026-06-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7b9c1d3e5f7'
down_revision: Union[str, None] = 'e5f7a9b1c3d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# MONEY columns are Numeric(14,2) in this app.
_MONEY = sa.Numeric(14, 2)


def upgrade() -> None:
    op.add_column('app_settings', sa.Column('trial_mode_enabled', sa.Boolean(), nullable=True))
    op.add_column('app_settings', sa.Column('premium_price', _MONEY, nullable=True))
    op.add_column('app_settings', sa.Column('membership_price', _MONEY, nullable=True))
    op.add_column('app_settings', sa.Column('name_change_price', _MONEY, nullable=True))
    op.add_column('app_settings', sa.Column('thread_title_price', _MONEY, nullable=True))
    op.add_column('app_settings', sa.Column('thread_autobump_price', _MONEY, nullable=True))
    # Backfill the single settings row with the existing defaults.
    op.execute("""
        UPDATE app_settings SET
            trial_mode_enabled = TRUE,
            premium_price = 80,
            membership_price = 50,
            name_change_price = 20,
            thread_title_price = 20,
            thread_autobump_price = 60
        WHERE trial_mode_enabled IS NULL
    """)


def downgrade() -> None:
    op.drop_column('app_settings', 'thread_autobump_price')
    op.drop_column('app_settings', 'thread_title_price')
    op.drop_column('app_settings', 'name_change_price')
    op.drop_column('app_settings', 'membership_price')
    op.drop_column('app_settings', 'premium_price')
    op.drop_column('app_settings', 'trial_mode_enabled')
