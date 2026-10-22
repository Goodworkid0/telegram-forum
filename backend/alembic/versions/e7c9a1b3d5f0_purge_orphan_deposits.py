"""purge orphan crypto_deposits with null order_id

These rows are abandoned/failed deposit attempts: the row is created when a user
requests a deposit address, but order_id is only assigned once the provider call
succeeds. A failed provider call used to leave the row committed with a null
order_id (now prevented in create_nowpayments_deposit). Such rows carry no funds
(never credited) and break the admin deposits list, so they are safe to delete.

Revision ID: e7c9a1b3d5f0
Revises: c4f6a8b0d2e4
Create Date: 2026-06-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e7c9a1b3d5f0'
down_revision: Union[str, None] = 'c4f6a8b0d2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Only ever touch un-credited, order_id-less rows — never a real deposit.
    op.execute(
        "DELETE FROM crypto_deposits "
        "WHERE order_id IS NULL AND COALESCE(is_credited, FALSE) = FALSE"
    )


def downgrade() -> None:
    # Irreversible: the deleted rows were failed attempts with no recoverable data.
    pass
