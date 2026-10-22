"""add_thread_upgrades

Thread cosmetic/paid upgrades: stand-out title color + glow, and bump tracking
(free manual 48h bump cooldown + paid auto-bump window).

Revision ID: e5f7a9b1c3d5
Revises: d4e6f8a0b2c4
Create Date: 2026-06-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f7a9b1c3d5'
down_revision: Union[str, None] = 'd4e6f8a0b2c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('threads', sa.Column('title_color', sa.String(), nullable=True))
    op.add_column('threads', sa.Column('title_glow', sa.Boolean(), nullable=True))
    op.add_column('threads', sa.Column('last_manual_bump_at', sa.DateTime(), nullable=True))
    op.add_column('threads', sa.Column('auto_bump_until', sa.DateTime(), nullable=True))
    op.add_column('threads', sa.Column('last_auto_bump_at', sa.DateTime(), nullable=True))
    op.execute("UPDATE threads SET title_glow = FALSE WHERE title_glow IS NULL")


def downgrade() -> None:
    op.drop_column('threads', 'last_auto_bump_at')
    op.drop_column('threads', 'auto_bump_until')
    op.drop_column('threads', 'last_manual_bump_at')
    op.drop_column('threads', 'title_glow')
    op.drop_column('threads', 'title_color')
