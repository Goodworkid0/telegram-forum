"""add_modaction_columns_and_auto_response

Revision ID: a7e3f1b9c2d4
Revises: f3562f2f4fe6
Create Date: 2026-06-17 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7e3f1b9c2d4'
down_revision: Union[str, None] = 'f3562f2f4fe6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('auto_response', sa.Text(), nullable=True))
    op.add_column('app_settings', sa.Column('support_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('mod_actions', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('mod_actions', sa.Column('thread_id', sa.Integer(), sa.ForeignKey('threads.id'), nullable=True))
    op.add_column('mod_actions', sa.Column('post_id', sa.Integer(), sa.ForeignKey('posts.id'), nullable=True))
    op.add_column('mod_actions', sa.Column('expires_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('mod_actions', 'expires_at')
    op.drop_column('mod_actions', 'post_id')
    op.drop_column('mod_actions', 'thread_id')
    op.drop_column('mod_actions', 'notes')
    op.drop_column('app_settings', 'support_user_id')
    op.drop_column('users', 'auto_response')
