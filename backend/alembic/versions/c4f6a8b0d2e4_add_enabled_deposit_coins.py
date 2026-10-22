"""add_enabled_deposit_coins_to_settings

Revision ID: c4f6a8b0d2e4
Revises: b2d4f6a8c0e2
Create Date: 2026-06-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f6a8b0d2e4'
down_revision: Union[str, None] = 'b2d4f6a8c0e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('app_settings', sa.Column('enabled_deposit_coins', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('app_settings', 'enabled_deposit_coins')
