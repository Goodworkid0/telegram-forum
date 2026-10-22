"""add shared_files table (bot file share)

Revision ID: e6f8a0b2c4d6
Revises: d5e7f9a1b3c5
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e6f8a0b2c4d6'
down_revision: Union[str, None] = 'd5e7f9a1b3c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guard — create_all already built the table on fresh DBs
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'shared_files' in insp.get_table_names():
        return

    op.create_table(
        'shared_files',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('file_unique_id', sa.String(128), nullable=False, unique=True, index=True),
        sa.Column('file_id', sa.Text(), nullable=False),
        sa.Column('kind', sa.String(16), nullable=False, server_default='document'),
        sa.Column('file_name', sa.String(300), nullable=True),
        sa.Column('mime_type', sa.String(128), nullable=True),
        sa.Column('file_size', sa.BigInteger(), nullable=True),  # a 2GB+ file overflows int4
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('uploader_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('uploader_tg_id', sa.String(32), nullable=True, index=True),
        sa.Column('retrieval_chat_id', sa.String(32), nullable=True),
        sa.Column('retrieval_message_id', sa.Integer(), nullable=True),
        sa.Column('backup_chat_id', sa.String(32), nullable=True),
        sa.Column('backup_message_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'APPROVED', 'REJECTED', name='sharedfilestatus'),
                  nullable=False, server_default='PENDING', index=True),
        sa.Column('reviewed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('reject_reason', sa.String(300), nullable=True),
        sa.Column('download_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True, index=True),
    )


def downgrade() -> None:
    op.drop_table('shared_files')
    # Drop the enum type on PostgreSQL (no-op on SQLite).
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        sa.Enum(name='sharedfilestatus').drop(bind, checkfirst=True)
