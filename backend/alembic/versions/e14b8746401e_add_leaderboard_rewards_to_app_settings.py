"""add_leaderboard_rewards_to_app_settings

Revision ID: e14b8746401e
Revises: e071f8f03791
Create Date: 2026-06-16 19:13:50.006039

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e14b8746401e'
down_revision: Union[str, None] = 'e071f8f03791'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE app_settings ADD COLUMN leaderboard_rewards VARCHAR")


def downgrade() -> None:
    op.execute("ALTER TABLE app_settings DROP COLUMN leaderboard_rewards")
