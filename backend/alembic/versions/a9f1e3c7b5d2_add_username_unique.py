"""add unique index on users.username

Closes a handle-squat race: username uniqueness was only ever enforced by a
non-atomic application-level check-then-write (auth.change_username / setup /
Telegram login sync), with no DB backstop, so two concurrent requests for the
same handle could both commit. The ORM now declares the column unique; this
migration adds the matching index on alembic-managed databases.

On a DB built fresh by create_all the unique index already exists (SQLAlchemy
builds it from the model), so CREATE UNIQUE INDEX IF NOT EXISTS is a no-op.
On an older alembic-stamped DB the index is absent and the check-then-write is
racy — this makes the database the source of truth.

Existing duplicate handles are de-conflicted first by suffixing all but the
lowest-id holder with _<id> (which is unique because id is), so the unique
index can be created without dropping any user rows.

Revision ID: a9f1e3c7b5d2
Revises: a7b9c1d3e5f7
Create Date: 2026-06-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a9f1e3c7b5d2'
down_revision: Union[str, None] = 'a7b9c1d3e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # De-conflict existing duplicate handles (NULLs are allowed and left alone),
    # keeping the lowest id per handle and suffixing the rest with _<id>.
    op.execute(
        "UPDATE users SET username = username || '_' || id "
        "WHERE username IS NOT NULL AND id NOT IN ("
        "  SELECT min_id FROM ("
        "    SELECT MIN(id) AS min_id FROM users WHERE username IS NOT NULL GROUP BY username"
        "  ) t"
        ")"
    )
    # Name matches SQLAlchemy's create_all index (unique=True, index=True ->
    # ix_users_username) so IF NOT EXISTS detects it on create_all-built DBs.
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)")


def downgrade() -> None:
    # Leave the unique index in place: dropping it re-opens the squat race, and
    # on create_all-built DBs the name belongs to a model constraint.
    pass
