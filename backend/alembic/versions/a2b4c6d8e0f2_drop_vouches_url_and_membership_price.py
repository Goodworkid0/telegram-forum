"""drop app_settings.vouches_url and membership_price

vouches_url: the vouch system was removed (see f1a3c5e7b9d1).
membership_price: the $50 membership upgrade endpoint was removed — the $80
premium purchase (premium_price) is the single self-serve upgrade path.

Revision ID: a2b4c6d8e0f2
Revises: f1a3c5e7b9d1
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a2b4c6d8e0f2'
down_revision: Union[str, None] = 'f1a3c5e7b9d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('app_settings') as batch:
        batch.drop_column('vouches_url')
        batch.drop_column('membership_price')


def downgrade() -> None:
    with op.batch_alter_table('app_settings') as batch:
        batch.add_column(sa.Column('vouches_url', sa.String(), nullable=True))
        batch.add_column(sa.Column('membership_price', sa.Numeric(14, 2), nullable=True))
