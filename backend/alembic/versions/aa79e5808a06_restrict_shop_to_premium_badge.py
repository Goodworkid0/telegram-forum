"""restrict_shop_to_premium_badge

Revision ID: aa79e5808a06
Revises: 7386c116a493
Create Date: 2026-06-16 19:07:36.335104

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa79e5808a06'
down_revision: Union[str, None] = '7386c116a493'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE badges SET is_purchasable = 0 WHERE name != 'Premium'")


def downgrade() -> None:
    op.execute("UPDATE badges SET is_purchasable = 1 WHERE name != 'Premium'")
