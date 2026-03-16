"""add atlassian oauth

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-16 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # atlassian_id on users for linking
    op.add_column("users", sa.Column("atlassian_id", sa.String(100), nullable=True))
    op.create_index("ix_users_atlassian_id", "users", ["atlassian_id"], unique=True)

    # Dedicated credential store (one row per user)
    op.create_table(
        "atlassian_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("cloud_id", sa.String(100), nullable=False),
        sa.Column("site_url", sa.String(255), nullable=False),
        sa.Column("site_name", sa.String(255), nullable=True),
        sa.Column("access_token_enc", sa.Text(), nullable=False),
        sa.Column("refresh_token_enc", sa.Text(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(), nullable=False),
        sa.Column("scopes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_atlassian_credentials_user_id", "atlassian_credentials", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_atlassian_credentials_user_id", table_name="atlassian_credentials"
    )
    op.drop_table("atlassian_credentials")
    op.drop_index("ix_users_atlassian_id", table_name="users")
    op.drop_column("users", "atlassian_id")
