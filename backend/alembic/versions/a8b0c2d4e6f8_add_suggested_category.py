"""add suggested_category_id to shared_files

Revision ID: a8b0c2d4e6f8
Revises: f7a9b1c3d5e7
Create Date: 2026-07-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a8b0c2d4e6f8'
down_revision: Union[str, None] = 'f7a9b1c3d5e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c['name'] for c in insp.get_columns('shared_files')]
    if 'suggested_category_id' not in cols:
        with op.batch_alter_table('shared_files') as batch:
            batch.add_column(sa.Column('suggested_category_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('shared_files') as batch:
        batch.drop_column('suggested_category_id')
