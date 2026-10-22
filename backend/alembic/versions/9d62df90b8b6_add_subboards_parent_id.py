"""add_subboards_parent_id

Revision ID: 9d62df90b8b6
Revises: 9c376302ce55
Create Date: 2026-06-16 19:07:56.667324

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d62df90b8b6'
down_revision: Union[str, None] = '9c376302ce55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE forum_boards ADD COLUMN parent_id INTEGER REFERENCES forum_boards(id)")


def downgrade() -> None:
    op.execute("ALTER TABLE forum_boards DROP COLUMN parent_id")
