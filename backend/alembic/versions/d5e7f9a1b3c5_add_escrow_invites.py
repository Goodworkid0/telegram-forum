"""add escrow_invites table

Shareable single-use codes for opening escrow deals without addressing the
counterparty by @handle (which may be hidden).

Revision ID: d5e7f9a1b3c5
Revises: c4d6e8f0a2b4
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd5e7f9a1b3c5'
down_revision: Union[str, None] = 'c4d6e8f0a2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guard — create_all already built this table on fresh DBs
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'escrow_invites' in insp.get_table_names():
        return

    op.create_table(
        'escrow_invites',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('code', sa.String(16), nullable=False, unique=True, index=True),
        sa.Column('creator_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('creator_role', sa.String(8), nullable=False),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('hold_days', sa.Integer(), nullable=True),
        sa.Column('used_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('deal_id', sa.Integer(), sa.ForeignKey('escrow_deals.id'), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('escrow_invites')
