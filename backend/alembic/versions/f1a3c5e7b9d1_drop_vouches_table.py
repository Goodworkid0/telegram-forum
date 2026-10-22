"""drop vouches table

The vouch system was removed: reputation (including rep between escrow deal
partners) replaced it, and trial upgrades are handled manually by admins.
The rep_positive counters that vouches contributed to are left untouched.

Revision ID: f1a3c5e7b9d1
Revises: e7c9a1b3d5f0
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f1a3c5e7b9d1'
down_revision: Union[str, None] = 'e7c9a1b3d5f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('vouches')


def downgrade() -> None:
    # Recreates the schema only; the dropped vouch rows are not recoverable.
    # Guard — create_all already built this table on fresh DBs
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'user_trust_levels' in insp.get_table_names():
        return

    op.create_table(
        'vouches',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('voucher_id', sa.Integer(), sa.ForeignKey('users.id'), index=True),
        sa.Column('vouchee_id', sa.Integer(), sa.ForeignKey('users.id'), index=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('voucher_id', 'vouchee_id', name='uq_vouch'),
    )
