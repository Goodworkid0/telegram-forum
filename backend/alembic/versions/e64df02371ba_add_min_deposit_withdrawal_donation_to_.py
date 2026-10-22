"""add_min_deposit_withdrawal_donation_to_settings

Revision ID: e64df02371ba
Revises: cee2376923b5
Create Date: 2026-06-21 01:06:35.027212

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e64df02371ba'
down_revision: Union[str, None] = 'cee2376923b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('app_settings', sa.Column('min_deposit_amount', sa.Float(), nullable=True))
    op.add_column('app_settings', sa.Column('min_withdrawal_amount', sa.Float(), nullable=True))
    op.add_column('app_settings', sa.Column('min_donation_amount', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('app_settings', 'min_donation_amount')
    op.drop_column('app_settings', 'min_withdrawal_amount')
    op.drop_column('app_settings', 'min_deposit_amount')
