"""add broadcast resume cursor (last_delivered_user_id)

Revision ID: c0d2e4f6a8b0
Revises: b9c1d3e5f7a9
Create Date: 2026-07-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c0d2e4f6a8b0'
down_revision: Union[str, None] = 'b9c1d3e5f7a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c['name'] for c in insp.get_columns('broadcasts')]
    if 'last_delivered_user_id' not in cols:
        with op.batch_alter_table('broadcasts') as batch:
            batch.add_column(sa.Column('last_delivered_user_id', sa.Integer(), nullable=True, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('broadcasts') as batch:
        batch.drop_column('last_delivered_user_id')
