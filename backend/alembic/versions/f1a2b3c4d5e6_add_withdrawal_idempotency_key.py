"""add withdrawal idempotency_key (and merge heads)

Adds withdrawal_requests.idempotency_key with a unique index to make withdrawal
submission idempotent. Also merges the two existing alembic heads
(3ea0d8b5aa27, e64df02371ba) into a single head.

Idempotent: safe to run even if the column/index were already created by the
app's startup compatibility patch (create_tables) in a dev environment.

Revision ID: f1a2b3c4d5e6
Revises: 3ea0d8b5aa27, e64df02371ba
Create Date: 2026-06-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = ('3ea0d8b5aa27', 'e64df02371ba')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = 'withdrawal_requests'
COLUMN = 'idempotency_key'
INDEX = 'ix_withdrawal_requests_idempotency_key'


def _has_column(insp, table: str, column: str) -> bool:
    try:
        return column in {c['name'] for c in insp.get_columns(table)}
    except Exception:
        return False


def _has_index(insp, table: str, index: str) -> bool:
    try:
        return index in {i['name'] for i in insp.get_indexes(table)}
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not _has_column(insp, TABLE, COLUMN):
        op.add_column(TABLE, sa.Column(COLUMN, sa.String(), nullable=True))
    # Refresh inspector view after the add, then create the unique index if missing.
    insp = sa.inspect(bind)
    if not _has_index(insp, TABLE, INDEX):
        op.create_index(INDEX, TABLE, [COLUMN], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if _has_index(insp, TABLE, INDEX):
        op.drop_index(INDEX, table_name=TABLE)
    if _has_column(insp, TABLE, COLUMN):
        op.drop_column(TABLE, COLUMN)
