"""add_mute_to_users

Revision ID: b2c4d6e8f0a1
Revises: a1b2c3d4e5f6
Create Date: 2026-06-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c4d6e8f0a1'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('is_muted', sa.Boolean(), nullable=True))
    op.add_column('users', sa.Column('mute_reason', sa.String(), nullable=True))
    op.add_column('users', sa.Column('muted_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('mute_expires_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('muted_by_id', sa.Integer(), nullable=True))
    op.execute("UPDATE users SET is_muted = FALSE WHERE is_muted IS NULL")


def downgrade() -> None:
    op.drop_column('users', 'muted_by_id')
    op.drop_column('users', 'mute_expires_at')
    op.drop_column('users', 'muted_at')
    op.drop_column('users', 'mute_reason')
    op.drop_column('users', 'is_muted')
