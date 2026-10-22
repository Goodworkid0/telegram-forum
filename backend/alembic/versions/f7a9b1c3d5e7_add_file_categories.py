"""add file categories

Revision ID: f7a9b1c3d5e7
Revises: e6f8a0b2c4d6
Create Date: 2026-07-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f7a9b1c3d5e7'
down_revision: Union[str, None] = 'e6f8a0b2c4d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Guard — create_all already built these on fresh DBs.
    if 'file_categories' not in insp.get_table_names():
        op.create_table(
            'file_categories',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('name', sa.String(80), nullable=False, unique=True),
            sa.Column('sort_order', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )

    cols = [c['name'] for c in insp.get_columns('shared_files')]
    if 'category_id' not in cols:
        with op.batch_alter_table('shared_files') as batch:
            batch.add_column(sa.Column('category_id', sa.Integer(), nullable=True))
            batch.create_index('ix_shared_files_category_id', ['category_id'])


def downgrade() -> None:
    with op.batch_alter_table('shared_files') as batch:
        batch.drop_index('ix_shared_files_category_id')
        batch.drop_column('category_id')
    op.drop_table('file_categories')
