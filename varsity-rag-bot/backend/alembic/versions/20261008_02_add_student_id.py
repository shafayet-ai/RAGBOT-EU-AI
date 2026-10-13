"""Add unique student IDs.

Revision ID: 20261008_02
Revises: 20261008_01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261008_02"
down_revision: Union[str, None] = "20261008_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("student_id", sa.String(length=32), nullable=True))
        batch_op.create_unique_constraint("uq_users_student_id", ["student_id"])


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_student_id", type_="unique")
        batch_op.drop_column("student_id")
