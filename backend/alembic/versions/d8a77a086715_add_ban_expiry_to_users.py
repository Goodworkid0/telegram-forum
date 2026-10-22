"""add_ban_expiry_to_users

Revision ID: d8a77a086715
Revises: 7673833ccca2
Create Date: 2026-06-16 19:07:50.157478

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8a77a086715'
down_revision: Union[str, None] = '7673833ccca2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN ban_expires_at DATETIME")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN ban_expires_at")
