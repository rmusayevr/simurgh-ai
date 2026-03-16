"""
AtlassianCredential model.

Stores per-user OAuth 2.0 (3LO) credentials for Atlassian (Jira + Confluence).
Access and refresh tokens are encrypted at rest using Fernet.

One row per user — the unique constraint on user_id enforces this.
The service layer uses upsert semantics when saving refreshed tokens.
"""

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship, Column, Text

if TYPE_CHECKING:
    from app.models.user import User


class AtlassianCredential(SQLModel, table=True):
    """
    Atlassian OAuth credential for a single user.

    Attributes:
        user_id:           FK to owning user (unique — one per user)
        cloud_id:          Atlassian site identifier (UUID)
        site_url:          e.g. https://your-org.atlassian.net
        site_name:         Human-readable site name (for display)
        access_token_enc:  Fernet-encrypted access token
        refresh_token_enc: Fernet-encrypted refresh token
        token_expires_at:  UTC expiry of the current access token
        scopes:            Comma-separated granted OAuth scopes
    """

    __tablename__ = "atlassian_credentials"

    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="users.id",
        unique=True,
        index=True,
        nullable=False,
        ondelete="CASCADE",
    )

    cloud_id: str = Field(max_length=100, nullable=False)
    site_url: str = Field(max_length=255, nullable=False)
    site_name: Optional[str] = Field(default=None, max_length=255)

    access_token_enc: str = Field(sa_column=Column(Text, nullable=False))
    refresh_token_enc: str = Field(sa_column=Column(Text, nullable=False))

    token_expires_at: datetime = Field(nullable=False)

    scopes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Comma-separated OAuth scopes granted by the user",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(timezone.utc).replace(tzinfo=None)
        },
    )

    # ── Relationships ──────────────────────────────────────────────────────────

    user: "User" = Relationship(
        back_populates="atlassian_credential",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    # ── Helpers ────────────────────────────────────────────────────────────────

    @property
    def is_expired(self) -> bool:
        """True if the access token has expired."""
        return datetime.now(timezone.utc).replace(tzinfo=None) >= self.token_expires_at

    @property
    def scope_list(self) -> list[str]:
        if not self.scopes:
            return []
        return [s.strip() for s in self.scopes.split(",") if s.strip()]

    def __repr__(self) -> str:
        return f"<AtlassianCredential(user_id={self.user_id}, site={self.site_url})>"
