"""drop dead columns found by the 2026-07 re-audit (round 2)

- users.email: never sent by the frontend, never displayed anywhere.
- users.trial_ends_at + app_settings.trial_period_days: trial is not
  time-limited — it ends only via premium purchase or manual admin upgrade.
- users.uses_custom_handle: custom handles removed — the @handle always
  mirrors Telegram; users only control its visibility (show_telegram).
- mod_actions.target_type / target_id: no creation site ever set them (always NULL).
- app_settings.referral_percent / referral_first_deposit_bonus_percent:
  superseded by referral_level1_percent / referral_level2_percent.
- app_settings.posts_per_page / threads_per_page: admin-editable but never
  enforced — page sizes come from the client. (max_posts_per_hour and
  max_threads_per_day ARE now enforced and stay.)

Revision ID: c4d6e8f0a2b4
Revises: b3c5d7e9f1a3
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c4d6e8f0a2b4'
down_revision: Union[str, None] = 'b3c5d7e9f1a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Registration counts as activity: backfill last_seen_at so no profile ever
    # shows "never" (new signups now set it at creation).
    op.execute("UPDATE users SET last_seen_at = created_at WHERE last_seen_at IS NULL")

    with op.batch_alter_table('users') as batch:
        batch.drop_column('email')
        batch.drop_column('trial_ends_at')
        batch.drop_column('uses_custom_handle')
    with op.batch_alter_table('mod_actions') as batch:
        batch.drop_column('target_type')
        batch.drop_column('target_id')
    with op.batch_alter_table('app_settings') as batch:
        batch.drop_column('referral_percent')
        batch.drop_column('referral_first_deposit_bonus_percent')
        batch.drop_column('posts_per_page')
        batch.drop_column('threads_per_page')
        batch.drop_column('trial_period_days')


def downgrade() -> None:
    with op.batch_alter_table('app_settings') as batch:
        batch.add_column(sa.Column('referral_percent', sa.Float(), nullable=True))
        batch.add_column(sa.Column('referral_first_deposit_bonus_percent', sa.Float(), nullable=True))
        batch.add_column(sa.Column('posts_per_page', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('threads_per_page', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('trial_period_days', sa.Integer(), nullable=True))
    with op.batch_alter_table('mod_actions') as batch:
        batch.add_column(sa.Column('target_type', sa.String(), nullable=True))
        batch.add_column(sa.Column('target_id', sa.Integer(), nullable=True))
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('email', sa.String(), nullable=True))
        batch.add_column(sa.Column('trial_ends_at', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('uses_custom_handle', sa.Boolean(), nullable=True))
