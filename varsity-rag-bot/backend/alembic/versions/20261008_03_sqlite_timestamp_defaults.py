"""Use portable timestamp defaults for SQLite and PostgreSQL.

Revision ID: 20261008_03
Revises: 20261008_02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261008_03"
down_revision: Union[str, None] = "20261008_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table_name in ("users", "chat_logs"):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                "created_at",
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )


def downgrade() -> None:
    for table_name in ("users", "chat_logs"):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                "created_at",
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
