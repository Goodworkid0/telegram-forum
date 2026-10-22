"""add_refresh_token_rotation_to_users

Revision ID: 5cf8d042a5b8
Revises: e14b8746401e
Create Date: 2026-06-16 19:34:34.251529

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5cf8d042a5b8'
down_revision: Union[str, None] = 'e14b8746401e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN refresh_token_family VARCHAR")
    op.execute("ALTER TABLE users ADD COLUMN refresh_token_version INTEGER DEFAULT 0")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN refresh_token_family")
    op.execute("ALTER TABLE users DROP COLUMN refresh_token_version")
