import re
from datetime import datetime
from typing import Optional
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)
from app.models.user import UserRole


# ==================== Validators ====================


def validate_password_strength(v: str) -> str:
    """Reusable password complexity validator."""
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one number")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
        raise ValueError("Password must contain at least one special character")
    return v


# ==================== Generic ====================


class Message(BaseModel):
    message: str


# ==================== Auth Schemas ====================


class UserCreate(BaseModel):
    """Schema for new user registration."""

    email: EmailStr
    password: str = Field(min_length=8)
    confirm_password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=100)
    job_title: Optional[str] = Field(default=None, max_length=100)
    terms_accepted: bool = Field(default=False)

    @field_validator("password")
    @classmethod
    def complexity(cls, v: str) -> str:
        return validate_password_strength(v)

    @field_validator("terms_accepted")
    @classmethod
    def must_accept_terms(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "You must accept the Terms of Service and Privacy Policy to register."
            )
        return v

    @model_validator(mode="after")
    def verify_password_match(self) -> "UserCreate":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class Token(BaseModel):
    """JWT token pair returned on successful login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: Optional[int] = None
    type: Optional[str] = None
    exp: Optional[int] = None


class RefreshTokenRequest(BaseModel):
    """Schema for refreshing access token."""

    refresh_token: str


class EmailVerificationRequest(BaseModel):
    """Schema for verifying email address."""

    token: str


class PasswordResetRequest(BaseModel):
    """Schema for requesting a password reset email."""

    email: EmailStr


class NewPassword(BaseModel):
    """Schema for setting a new password via reset token."""

    token: str
    new_password: str = Field(min_length=8)
    confirm_new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def complexity(cls, v: str) -> str:
        return validate_password_strength(v)

    @model_validator(mode="after")
    def verify_match(self) -> "NewPassword":
        if self.new_password != self.confirm_new_password:
            raise ValueError("Passwords do not match")
        return self


# Alias for consistency with auth.py endpoint naming
PasswordResetConfirm = NewPassword


class ChangePasswordRequest(BaseModel):
    """Schema for authenticated password change."""

    current_password: str
    new_password: str = Field(min_length=8)
    confirm_new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def complexity(cls, v: str) -> str:
        return validate_password_strength(v)

    @model_validator(mode="after")
    def verify_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_new_password:
            raise ValueError("New passwords do not match")
        return self


# ==================== User Read Schemas ====================


class UserRead(BaseModel):
    """Full user profile returned to the authenticated user themselves."""

    id: int
    email: str
    full_name: Optional[str]
    job_title: Optional[str]
    avatar_url: Optional[str]
    role: UserRole
    is_active: bool
    is_superuser: bool
    email_verified: bool
    terms_accepted: bool
    last_login: Optional[datetime]
    login_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserMinimalRead(BaseModel):
    """Minimal user info for embedding in other responses (e.g. project members)."""

    id: int
    full_name: Optional[str]
    avatar_url: Optional[str]
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


# ==================== User Update Schemas ====================


class UserUpdate(BaseModel):
    """
    Schema for user updating their own profile (used in PATCH /auth/me).
    Alias for UserProfileUpdate for backward compatibility.
    """

    full_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    job_title: Optional[str] = Field(default=None, max_length=100)
    avatar_url: Optional[str] = Field(default=None, max_length=500)


class UserProfileUpdate(BaseModel):
    """
    Schema for a user updating their own profile.
    Excludes privileged fields (role, is_active, is_superuser).
    """

    full_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    job_title: Optional[str] = Field(default=None, max_length=100)
    avatar_url: Optional[str] = Field(default=None, max_length=500)


class AdminUserUpdate(BaseModel):
    """
    Schema for admin updating any user account.
    Includes privileged fields not available to regular users.
    """

    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    job_title: Optional[str] = Field(default=None, max_length=100)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None


# ==================== Admin Schemas ====================


class AdminUserResponse(BaseModel):
    """Full user record for admin panel views."""

    id: int
    email: str
    full_name: Optional[str]
    job_title: Optional[str]
    is_active: bool
    is_superuser: bool
    email_verified: bool
    role: UserRole
    login_count: int
    last_login: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminProjectResponse(BaseModel):
    """Project summary for admin panel views."""

    id: int
    name: str
    description: Optional[str] = None
    owner_email: str
    created_at: Optional[datetime] = None
    proposal_count: int = 0
    document_count: int = 0
    member_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class AdminParticipantCreate(BaseModel):
    """Schema for admin-created study participant accounts."""

    email: str
    password: str = Field(min_length=6)
    full_name: Optional[str] = None
