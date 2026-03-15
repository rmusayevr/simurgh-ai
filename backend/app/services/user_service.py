"""
User service for authentication, registration, and account management.

Handles all business logic related to users:
    - Registration with email verification
    - Authentication (login, token refresh, logout)
    - Password management (change, reset)
    - Profile management
    - Admin user management (role, activation)

All database operations are async using SQLModel + AsyncSession.
JWT and password utilities are delegated to app.core.security.
"""

import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, List

import structlog
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import User, UserRole
from app.models.token import RefreshToken
from app.schemas.user import (
    UserCreate,
    UserProfileUpdate,
    AdminUserUpdate,
    ChangePasswordRequest,
    NewPassword,
)
from app.core.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
)
from app.core.exceptions import (
    NotFoundException,
    ConflictException,
    UnauthorizedException,
    BadRequestException,
)

logger = structlog.get_logger(__name__)


class UserService:
    """
    Service layer for all user-related business logic.

    All methods are async and require an AsyncSession.
    Raises domain exceptions from app.core.exceptions
    (NotFoundException, ConflictException, etc.) which are
    handled centrally in main.py.

    JWT and password hashing are delegated to app.core.security
    to avoid duplication.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== Helpers ====================

    async def get_by_id(self, user_id: int) -> User:
        """
        Fetch a user by primary key.

        Raises:
            NotFoundException: If user not found
        """
        user = await self.db.get(User, user_id)
        if not user:
            raise NotFoundException("User not found")
        return user

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Fetch a user by email address.

        Args:
            email: User's email address

        Returns:
            User | None: Found user or None
        """
        result = await self.db.exec(select(User).where(User.email == email.lower()))
        return result.first()

    async def get_by_verification_token(self, token: str) -> Optional[User]:
        """Fetch a user by email verification token."""
        result = await self.db.exec(
            select(User).where(User.verification_token == token)
        )
        return result.first()

    async def get_by_reset_token(self, token: str) -> Optional[User]:
        """Fetch a user by password reset token."""
        result = await self.db.exec(select(User).where(User.reset_token == token))
        return result.first()

    # ==================== Registration ====================

    async def register(self, data: UserCreate) -> User:
        """
        Register a new user account.

        Creates the user with a hashed password and a verification
        token. Account is inactive until email is verified.

        Args:
            data: Registration form data

        Returns:
            User: Newly created user

        Raises:
            HTTPException 409: If email already registered
        """
        existing = await self.get_by_email(data.email)
        if existing:
            raise ConflictException("An account with this email already exists")

        user = User(
            email=data.email.lower(),
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            job_title=data.job_title,
            is_active=False,
            email_verified=False,
            verification_token=secrets.token_urlsafe(32),
            role=UserRole.USER,
            terms_accepted=data.terms_accepted,
            terms_accepted_at=(
                datetime.now(timezone.utc).replace(tzinfo=None)
                if data.terms_accepted
                else None
            ),
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    # ==================== Email Verification ====================

    async def verify_email(self, token: str) -> User:
        """
        Verify a user's email address using their verification token.

        Activates the account on success.

        Args:
            token: Email verification token

        Returns:
            User: Verified and activated user

        Raises:
            HTTPException 400: If token is invalid or already used
        """
        user = await self.get_by_verification_token(token)
        if not user:
            raise BadRequestException("Invalid or expired verification token")

        if user.email_verified:
            raise BadRequestException("Email already verified")

        user.verify_email()  # sets email_verified=True, is_active=True
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    # ==================== Authentication ====================

    async def authenticate(self, email: str, password: str) -> User:
        """
        Authenticate a user with email and password.

        Distinguishes between wrong credentials and unverified/inactive
        account to give the user actionable feedback.

        Raises:
            HTTPException 401: If credentials invalid or account not loginable
        """
        user = await self.get_by_email(email)

        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedException("Invalid email or password")

        if not user.can_login:
            if not user.email_verified:
                raise UnauthorizedException(
                    "Please verify your email address before logging in"
                )
            raise UnauthorizedException("Account is inactive. Please contact support")

        user.update_last_login()  # increments login_count, sets last_login
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info("user_authenticated", user_id=user.id)
        return user

    async def issue_tokens(self, user_id: int) -> tuple[str, str]:
        """
        Issue a new access + refresh token pair for a user.

        Stores the refresh token in the DB for revocation tracking.
        Uses create_access_token and create_refresh_token from security.py.

        Returns:
            tuple: (access_token, refresh_token_value)
        """
        # Both delegated to security.py
        access_token = create_access_token(subject=user_id)
        refresh_token_value = create_refresh_token(subject=user_id)

        token_record = RefreshToken(
            user_id=user_id,
            token=refresh_token_value,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.db.add(token_record)
        await self.db.commit()

        return access_token, refresh_token_value

    async def refresh_access_token(self, refresh_token_value: str) -> str:
        """
        Validate a refresh token and issue a new access token.

        Raises:
            HTTPException 401: If token invalid, expired, or revoked
        """
        result = await self.db.exec(
            select(RefreshToken).where(
                RefreshToken.token == refresh_token_value,
                RefreshToken.revoked_at.is_(None),
            )
        )
        token_record = result.first()

        if not token_record:
            raise UnauthorizedException("Invalid or revoked refresh token")

        # Compare using naive datetime (remove timezone from now())
        if token_record.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
            raise UnauthorizedException(
                "Refresh token has expired. Please log in again"
            )

        # create_access_token delegated to security.py
        new_access_token = create_access_token(subject=token_record.user_id)

        logger.info("access_token_refreshed", user_id=token_record.user_id)
        return new_access_token

    async def revoke_refresh_token(self, refresh_token_value: str) -> None:
        """Revoke a single refresh token (single device logout)."""
        result = await self.db.exec(
            select(RefreshToken).where(RefreshToken.token == refresh_token_value)
        )
        token_record = result.first()
        if token_record:
            token_record.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
            self.db.add(token_record)
            await self.db.commit()
            logger.info("refresh_token_revoked", user_id=token_record.user_id)

    async def revoke_all_user_tokens(self, user_id: int) -> None:
        """
        Revoke all refresh tokens for a user (logout all devices).
        Called on password change, password reset, and account deactivation.
        """
        result = await self.db.exec(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        tokens = result.all()
        for token in tokens:
            token.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
            self.db.add(token)
        await self.db.commit()
        logger.info("all_tokens_revoked", user_id=user_id, count=len(tokens))

    async def change_password(
        self,
        user_id: int,
        data: ChangePasswordRequest,
    ) -> User:
        """
        Change authenticated user's own password.

        Verifies current password before updating.
        Revokes all refresh tokens to force re-login on other devices.

        Raises:
            HTTPException 400: If current password incorrect
        """
        user = await self.get_by_id(user_id)

        if not verify_password(data.current_password, user.hashed_password):
            raise BadRequestException("Current password is incorrect")

        user.hashed_password = hash_password(data.new_password)
        user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.add(user)

        await self.revoke_all_user_tokens(user_id)

        await self.db.commit()
        await self.db.refresh(user)

        logger.info("password_changed", user_id=user_id)
        return user

    async def request_password_reset(self, email: str) -> Optional[User]:
        """
        Generate a password reset token for a user.

        Intentionally returns None silently if email not found
        to prevent email enumeration attacks. Route should
        always return HTTP 200 regardless of outcome.
        """
        user = await self.get_by_email(email)
        if not user:
            logger.info("password_reset_requested_unknown_email")
            return None

        user.reset_token = secrets.token_urlsafe(32)
        user.reset_token_expires_at = datetime.now(timezone.utc).replace(
            tzinfo=None
        ) + timedelta(hours=settings.PASSWORD_RESET_EXPIRE_HOURS)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info("password_reset_token_generated", user_id=user.id)
        return user

    async def reset_password(self, data: NewPassword) -> User:
        """
        Reset a user's password using a valid reset token.

        Revokes all refresh tokens after successful reset.

        Raises:
            HTTPException 400: If token invalid or expired
        """
        user = await self.get_by_reset_token(data.token)

        if not user:
            raise BadRequestException("Invalid or expired reset token")

        if (
            not user.reset_token_expires_at
            or user.reset_token_expires_at
            < datetime.now(timezone.utc).replace(tzinfo=None)
        ):
            raise BadRequestException(
                "Reset token has expired. Please request a new one"
            )

        user.hashed_password = hash_password(data.new_password)
        user.clear_reset_token()
        user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.add(user)

        await self.revoke_all_user_tokens(user.id)

        await self.db.commit()
        await self.db.refresh(user)

        logger.info("password_reset_completed", user_id=user.id)
        return user

    # ==================== Profile Management ====================

    async def update_profile(
        self,
        user_id: int,
        data: UserProfileUpdate,
    ) -> User:
        """
        Update a user's own profile (non-privileged fields only).
        Uses model_dump(exclude_unset=True) so only provided fields update.
        """
        user = await self.get_by_id(user_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info("profile_updated", user_id=user_id, fields=list(update_data.keys()))
        return user

    async def accept_terms(self, user_id: int) -> User:
        """Record user's acceptance of terms of service."""
        user = await self.get_by_id(user_id)
        user.terms_accepted = True
        user.terms_accepted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    # ==================== Admin Operations ====================

    async def admin_update_user(
        self,
        user_id: int,
        data: AdminUserUpdate,
    ) -> User:
        """
        Admin update of any user account including privileged fields.

        Raises:
            HTTPException 404: If user not found
            HTTPException 409: If new email already taken
        """
        user = await self.get_by_id(user_id)

        if data.email and data.email.lower() != user.email:
            existing = await self.get_by_email(data.email)
            if existing:
                raise ConflictException("Email already in use by another account")

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "email" and value:
                setattr(user, field, value.lower())
            else:
                setattr(user, field, value)

        user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info("admin_user_updated", target_user_id=user_id)
        return user

    async def admin_list_users(
        self,
        skip: int = 0,
        limit: int = 50,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
    ) -> List[User]:
        """List all users with optional filtering (admin only)."""
        query = select(User)

        if role is not None:
            query = query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)

        query = query.offset(skip).limit(limit).order_by(User.created_at.desc())

        result = await self.db.exec(query)
        return result.all()

    async def admin_delete_user(self, user_id: int, requesting_admin_id: int) -> None:
        """
        Permanently delete a user account and all associated data (admin only).

        Admins cannot delete their own account via this method (prevents lockout).
        Cascade deletes handle: owned_projects, stakeholder_links, refresh_tokens.

        Args:
            user_id: ID of the account to delete
            requesting_admin_id: ID of the admin making the request

        Raises:
            BadRequestException: If admin tries to delete their own account
            NotFoundException: If user does not exist
        """
        if user_id == requesting_admin_id:
            raise BadRequestException(
                "Admins cannot delete their own account via this endpoint"
            )

        user = await self.get_by_id(user_id)

        await self.revoke_all_user_tokens(user_id)

        await self.db.delete(user)
        await self.db.commit()

        logger.warning(
            "admin_user_deleted",
            deleted_user_id=user_id,
            requesting_admin_id=requesting_admin_id,
        )

    async def admin_deactivate_user(self, user_id: int) -> User:
        """
        Deactivate a user account and revoke all tokens (admin only).
        User will be immediately logged out of all devices.
        """
        user = await self.get_by_id(user_id)
        user.is_active = False
        user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.add(user)

        await self.revoke_all_user_tokens(user_id)

        await self.db.commit()
        await self.db.refresh(user)

        logger.info("user_deactivated", user_id=user_id)
        return user

    async def admin_activate_user(self, user_id: int) -> User:
        """Reactivate a deactivated user account (admin only)."""
        user = await self.get_by_id(user_id)
        user.is_active = True
        user.updated_at = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info("user_activated", user_id=user_id)
        return user

    # ==================== GDPR: Account Deletion ====================

    async def delete_account(self, user_id: int, password: str) -> None:
        """
        Permanently delete a user account and all associated data.

        Requires the user's current password as confirmation to prevent
        accidental or unauthorised deletion.

        Cascades handled by the ORM (owned_projects, stakeholder_links,
        refresh_tokens are all cascade="all, delete-orphan").

        Args:
            user_id: ID of the account to delete
            password: Current password for confirmation

        Raises:
            UnauthorizedException: If password is incorrect
            NotFoundException: If user does not exist
        """
        user = await self.get_by_id(user_id)

        if not verify_password(password, user.hashed_password):
            logger.warning("delete_account_wrong_password", user_id=user_id)
            raise UnauthorizedException(
                "Incorrect password. Account deletion cancelled."
            )

        await self.db.delete(user)
        await self.db.commit()

        logger.info("account_deleted", user_id=user_id)

    # ==================== GDPR: Data Export ====================

    async def export_my_data(self, user_id: int) -> dict:
        """
        Export all personal data held for a user as a JSON-serialisable dict.

        Covers GDPR Article 20 (right to data portability). Includes profile,
        account metadata, and owned projects. Sensitive fields (hashed password,
        tokens) are intentionally excluded.

        Args:
            user_id: ID of the user requesting export

        Returns:
            dict: All personal data in a portable JSON structure
        """
        user = await self.get_by_id(user_id)

        projects = [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "tags": p.tags,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in (user.owned_projects or [])
        ]

        return {
            "export_generated_at": datetime.now(timezone.utc).isoformat(),
            "profile": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "job_title": user.job_title,
                "avatar_url": user.avatar_url,
                "role": user.role.value if user.role else None,
            },
            "account": {
                "is_active": user.is_active,
                "email_verified": user.email_verified,
                "terms_accepted": user.terms_accepted,
                "terms_accepted_at": (
                    user.terms_accepted_at.isoformat()
                    if user.terms_accepted_at
                    else None
                ),
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "login_count": user.login_count,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None,
            },
            "projects": projects,
        }
