"""
Authentication token models.

Manages refresh tokens for JWT-based authentication with support
for multi-device sessions and token revocation.

Relationships:
    RefreshToken -> User (many tokens per user, one per device)
"""

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship, Column, String
from sqlalchemy import Index

if TYPE_CHECKING:
    from app.models.user import User


class RefreshToken(SQLModel, table=True):
    """
    Refresh token for JWT authentication.

    Supports multi-device sessions by allowing multiple active tokens
    per user. Tokens can be individually revoked (e.g., on logout)
    or all revoked at once (e.g., on password change).

    Attributes:
        id: Primary key
        token: Unique token string (hashed for security)
        expires_at: Token expiration timestamp
        revoked_at: Revocation timestamp (null if active)
        user_agent: Client user agent string
        ip_address: Client IP address
        device_name: Human-readable device identifier
        is_remember_me: Whether token was created with "remember me"
        user_id: FK to owning user
        created_at: Token creation timestamp
        last_used_at: Last time token was used
    """

    __tablename__ = "refresh_tokens"

    # ==================== Primary Key ====================

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Token ID",
    )

    # ==================== Token Data ====================

    token: str = Field(
        sa_column=Column(
            String(512),
            nullable=False,
            unique=True,
            index=True,
        ),
        max_length=512,
        description="Unique token string (store hashed in production)",
    )

    # ==================== Expiration ====================

    expires_at: datetime = Field(
        nullable=False,
        index=True,
        description="Token expiration timestamp (UTC)",
    )

    # ==================== Revocation ====================

    revoked_at: Optional[datetime] = Field(
        default=None,
        description="Revocation timestamp (null if active)",
    )

    revocation_reason: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Reason for revocation (logout/password_changed/admin)",
    )

    # ==================== Device Info ====================

    user_agent: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Client user agent string",
    )

    ip_address: Optional[str] = Field(
        default=None,
        max_length=45,  # IPv6 max length
        description="Client IP address (IPv4 or IPv6)",
    )

    device_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Human-readable device name (e.g., 'Chrome on MacOS')",
    )

    # ==================== Session Flags ====================

    is_remember_me: bool = Field(
        default=False,
        description="Whether created with 'remember me' (longer expiry)",
    )

    # ==================== Foreign Keys ====================

    user_id: int = Field(
        foreign_key="users.id",
        index=True,
        nullable=False,
        description="Owning user ID",
        ondelete="CASCADE",
    )

    # ==================== Timestamps ====================

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        index=True,
        description="Token creation timestamp (UTC)",
    )

    last_used_at: Optional[datetime] = Field(
        default=None,
        description="Last time token was used for authentication",
    )

    # ==================== Relationships ====================

    user: "User" = Relationship(
        back_populates="refresh_tokens",
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    # ==================== Indexes ====================

    __table_args__ = (
        Index("idx_refresh_token_user_active", "user_id", "revoked_at"),
        Index("idx_refresh_token_expires", "expires_at", "revoked_at"),
        Index("idx_refresh_token_created", "user_id", "created_at"),
    )

    # ==================== Helper Methods ====================

    @property
    def is_revoked(self) -> bool:
        """Check if token has been revoked."""
        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.now(timezone.utc) >= self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not expired and not revoked)."""
        return not self.is_expired and not self.is_revoked

    @property
    def expires_in_seconds(self) -> float:
        """Get seconds until expiration (negative if expired)."""
        delta = self.expires_at - datetime.now(timezone.utc).replace(tzinfo=None)
        return delta.total_seconds()

    def revoke(self, reason: str = "logout") -> None:
        """
        Revoke this token.

        Args:
            reason: Reason for revocation
        """
        self.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.revocation_reason = reason

    def record_usage(self) -> None:
        """Record that this token was used."""
        self.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<RefreshToken("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"valid={self.is_valid}"
            f")>"
        )
