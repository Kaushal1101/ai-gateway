"""add embedding to request_log

Revision ID: 212dd41bd4ba
Revises: 90a3d5207239
Create Date: 2026-08-03 11:58:07.059846

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "212dd41bd4ba"
down_revision: Union[str, Sequence[str], None] = "90a3d5207239"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("request_logs", sa.Column("embedding", Vector(768), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("request_logs", "embedding")
