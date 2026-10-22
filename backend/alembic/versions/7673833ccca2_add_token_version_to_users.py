"""add_token_version_to_users

Revision ID: 7673833ccca2
Revises: aa79e5808a06
Create Date: 2026-06-16 19:07:46.598749

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7673833ccca2'
down_revision: Union[str, None] = 'aa79e5808a06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN token_version INTEGER DEFAULT 0")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN token_version")
