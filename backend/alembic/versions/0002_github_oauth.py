"""add github oauth fields to users

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-15 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("github_id", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("github_username", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("oauth_provider", sa.String(20), nullable=True))

    op.create_index("ix_users_github_id", "users", ["github_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_github_id", table_name="users")
    op.drop_column("users", "oauth_provider")
    op.drop_column("users", "github_username")
    op.drop_column("users", "github_id")
