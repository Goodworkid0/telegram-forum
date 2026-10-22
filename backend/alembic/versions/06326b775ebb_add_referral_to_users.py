"""add_referral_to_users

Revision ID: 06326b775ebb
Revises: 336b7b2cbc25
Create Date: 2026-06-16 19:07:50.962536

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '06326b775ebb'
down_revision: Union[str, None] = '336b7b2cbc25'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN referral_code VARCHAR")
    op.execute("ALTER TABLE users ADD COLUMN referred_by_id INTEGER REFERENCES users(id)")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN referred_by_id")
    op.execute("ALTER TABLE users DROP COLUMN referral_code")
