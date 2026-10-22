"""add_daily_reward_config

Revision ID: 46f6ece172e2
Revises: 9d62df90b8b6
Create Date: 2026-06-16 19:07:56.938558

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '46f6ece172e2'
down_revision: Union[str, None] = '9d62df90b8b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS daily_reward_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day INTEGER NOT NULL UNIQUE,
            xp_amount INTEGER DEFAULT 10,
            balance_amount FLOAT DEFAULT 0.10,
            badge_id INTEGER REFERENCES badges(id),
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS daily_reward_config")
