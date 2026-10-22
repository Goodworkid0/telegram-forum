"""add_badge_rewards

Revision ID: dd2633c52b86
Revises: 0b3d6d83b482
Create Date: 2026-06-16 19:07:55.905041

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd2633c52b86'
down_revision: Union[str, None] = '0b3d6d83b482'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE badges ADD COLUMN reward_xp INTEGER DEFAULT 0")
    op.execute("ALTER TABLE badges ADD COLUMN reward_balance FLOAT DEFAULT 0.0")
    op.execute("ALTER TABLE badges ADD COLUMN reward_role VARCHAR")
    op.execute("ALTER TABLE badges ADD COLUMN multi_purchase BOOLEAN DEFAULT 0")
    op.execute("ALTER TABLE badges ADD COLUMN icon VARCHAR")
    op.execute("ALTER TABLE badges ADD COLUMN icon_style VARCHAR DEFAULT 'default'")


def downgrade() -> None:
    op.execute("ALTER TABLE badges DROP COLUMN icon_style")
    op.execute("ALTER TABLE badges DROP COLUMN icon")
    op.execute("ALTER TABLE badges DROP COLUMN multi_purchase")
    op.execute("ALTER TABLE badges DROP COLUMN reward_role")
    op.execute("ALTER TABLE badges DROP COLUMN reward_balance")
    op.execute("ALTER TABLE badges DROP COLUMN reward_xp")
