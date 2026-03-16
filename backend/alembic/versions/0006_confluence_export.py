"""add confluence export fields to proposals

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-16 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "proposals", sa.Column("confluence_page_id", sa.String(50), nullable=True)
    )
    op.add_column(
        "proposals", sa.Column("confluence_page_url", sa.String(500), nullable=True)
    )
    op.add_column(
        "proposals", sa.Column("confluence_space_key", sa.String(50), nullable=True)
    )
    op.add_column(
        "proposals", sa.Column("confluence_exported_at", sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("proposals", "confluence_exported_at")
    op.drop_column("proposals", "confluence_space_key")
    op.drop_column("proposals", "confluence_page_url")
    op.drop_column("proposals", "confluence_page_id")
