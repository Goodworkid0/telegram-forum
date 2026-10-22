"""add_user_badge_quantity

Revision ID: 33e15431ca6a
Revises: dd2633c52b86
Create Date: 2026-06-16 19:07:56.152533

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '33e15431ca6a'
down_revision: Union[str, None] = 'dd2633c52b86'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_badges ADD COLUMN quantity INTEGER DEFAULT 1")


def downgrade() -> None:
    op.execute("ALTER TABLE user_badges DROP COLUMN quantity")
