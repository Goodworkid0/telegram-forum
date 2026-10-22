"""add_show_telegram_to_users

Revision ID: 7386c116a493
Revises: 
Create Date: 2026-06-12 02:18:11.990635

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7386c116a493'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('show_telegram', sa.Boolean(), nullable=True))
    op.execute("UPDATE users SET show_telegram = 1 WHERE show_telegram IS NULL")


def downgrade() -> None:
    op.drop_column('users', 'show_telegram')
