"""add jira export fields to proposals

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-16 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("proposals", sa.Column("jira_epic_key", sa.String(50), nullable=True))
    op.add_column(
        "proposals", sa.Column("jira_epic_url", sa.String(500), nullable=True)
    )
    op.add_column(
        "proposals", sa.Column("jira_project_key", sa.String(20), nullable=True)
    )
    op.add_column(
        "proposals", sa.Column("jira_exported_at", sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("proposals", "jira_exported_at")
    op.drop_column("proposals", "jira_project_key")
    op.drop_column("proposals", "jira_epic_url")
    op.drop_column("proposals", "jira_epic_key")
