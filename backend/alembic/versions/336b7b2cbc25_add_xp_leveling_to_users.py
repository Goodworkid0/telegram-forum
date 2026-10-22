"""add_xp_leveling_to_users

Revision ID: 336b7b2cbc25
Revises: d525ba42ab46
Create Date: 2026-06-16 19:07:50.703396

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '336b7b2cbc25'
down_revision: Union[str, None] = 'd525ba42ab46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN xp INTEGER DEFAULT 0")
    op.execute("ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 1")
    op.execute("ALTER TABLE users ADD COLUMN login_streak INTEGER DEFAULT 0")
    op.execute("ALTER TABLE users ADD COLUMN last_login_date DATETIME")
    op.execute("ALTER TABLE users ADD COLUMN streak_bonus_claimed BOOLEAN DEFAULT 0")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN streak_bonus_claimed")
    op.execute("ALTER TABLE users DROP COLUMN last_login_date")
    op.execute("ALTER TABLE users DROP COLUMN login_streak")
    op.execute("ALTER TABLE users DROP COLUMN level")
    op.execute("ALTER TABLE users DROP COLUMN xp")
