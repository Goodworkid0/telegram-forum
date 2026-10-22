"""add_premium_to_users

Revision ID: 9c376302ce55
Revises: 33e15431ca6a
Create Date: 2026-06-16 19:07:56.399179

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c376302ce55'
down_revision: Union[str, None] = '33e15431ca6a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN is_premium BOOLEAN DEFAULT 0")
    op.execute("ALTER TABLE users ADD COLUMN premium_until DATETIME")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN premium_until")
    op.execute("ALTER TABLE users DROP COLUMN is_premium")
