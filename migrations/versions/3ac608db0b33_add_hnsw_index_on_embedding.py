"""add hnsw index on embedding

Revision ID: 3ac608db0b33
Revises: 212dd41bd4ba
Create Date: 2026-09-06 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3ac608db0b33"
down_revision: Union[str, Sequence[str], None] = "212dd41bd4ba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_request_logs_embedding_hnsw "
        "ON request_logs USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_request_logs_embedding_hnsw")
