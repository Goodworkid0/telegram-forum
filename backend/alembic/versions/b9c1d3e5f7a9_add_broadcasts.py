"""add broadcasts table (admin advertisements)

Revision ID: b9c1d3e5f7a9
Revises: a8b0c2d4e6f8
Create Date: 2026-07-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b9c1d3e5f7a9'
down_revision: Union[str, None] = 'a8b0c2d4e6f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'broadcasts' in insp.get_table_names():
        return
    op.create_table(
        'broadcasts',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('link', sa.String(500), nullable=True),
        sa.Column('send_inbox', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('send_bot', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column('target_role', sa.String(16), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'SENDING', 'DONE', 'FAILED', name='broadcaststatus'),
                  nullable=False, server_default='PENDING', index=True),
        sa.Column('total_recipients', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('sent_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('failed_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, index=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('broadcasts')
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        sa.Enum(name='broadcaststatus').drop(bind, checkfirst=True)
