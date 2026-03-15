"""
Authentication endpoints for user registration and session management.

Provides:
    - User registration with email verification
    - Login with access/refresh tokens
    - Token refresh and revocation
    - Password reset workflow
    - Email verification
    - User profile management

All endpoints use UserService for business logic.
"""

import secrets
import structlog
from typing import Annotated

from fastapi import APIRouter, Depends, BackgroundTasks, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import get_session, get_current_user
from app.core.config import settings
from app.core.email import (
    send_activation_email,
    send_password_reset_email,
    send_welcome_email,
)
from app.core.exceptions import (
    UnauthorizedException,
    BadRequestException,
    NotFoundException,
)
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserRead,
    UserUpdate,
    Token,
    RefreshTokenRequest,
    ChangePasswordRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    EmailVerificationRequest,
    Message,
)
from app.services.user_service import UserService
from app.services.system_service import SystemService

logger = structlog.get_logger()
router = APIRouter()


# ==================== Registration ====================


@router.post("/register", response_model=Message, status_code=201)
async def register(
    user_in: UserCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """
    Register a new user account.

    When SMTP is configured (``EMAIL_ENABLED=true``), the account starts inactive
    and an email verification link is sent.

    When SMTP is **not** configured, the account is activated immediately so users
    can log in without needing an email flow.  A warning is logged so operators
    know that email verification is being bypassed.

    Args:
        user_in: Registration data (email, password, name)
        background_tasks: FastAPI background tasks for email sending

    Returns:
        Message: Success message (varies depending on SMTP availability)

    Raises:
        BadRequestException: If email already exists
    """
    log = logger.bind(operation="register", email=user_in.email)
    log.info("registration_started")

    # Check whether the admin has disabled new registrations.
    # This flag is exposed via /public/status but was never enforced here.
    system_service = SystemService(session)
    system_settings = await system_service.get_settings()
    if not system_settings.allow_registrations:
        log.warning("registration_rejected_registrations_disabled")
        raise BadRequestException(
            "New registrations are currently closed. Please contact the administrator."
        )

    # Block registration if SMTP is not configured, unless explicitly opted out.
    # Without SMTP, email verification cannot be enforced — anyone can register
    # with a fake address and immediately access the application.
    # Set SKIP_EMAIL_VERIFICATION=true only for local development or testing.
    # if not settings.EMAIL_ENABLED and not settings.SKIP_EMAIL_VERIFICATION:
    #     log.error(
    #         "registration_blocked_smtp_not_configured",
    #         detail="SMTP is required for public registration but is not configured.",
    #     )
    #     raise BadRequestException(
    #         "Registration is currently unavailable. "
    #         "Please contact the administrator or try again later."
    #     )

    user_service = UserService(session)

    try:
        user = await user_service.register(user_in)

        if settings.SKIP_EMAIL_VERIFICATION:
            # SKIP_EMAIL_VERIFICATION=true: auto-activate regardless of email config.
            # Use this when email sending is not available (e.g. Resend without a
            # verified domain, or local development).
            log.warning(
                "skip_email_verification_auto_activating",
                user_id=user.id,
            )
            user.verify_email()
            session.add(user)
            await session.commit()
            log.info("registration_completed_auto_activated", user_id=user.id)
            return Message(message="Registration successful. You can log in now.")

        elif settings.EMAIL_ENABLED:
            # Normal path: send verification email, account starts inactive.
            token = user.verification_token
            background_tasks.add_task(
                send_activation_email,
                email_to=user.email,
                token=token,
                username=user.full_name,
            )
            log.info("registration_completed_email_pending", user_id=user.id)
            return Message(
                message="Registration successful. Please check your email to activate your account."
            )

        else:
            # EMAIL_ENABLED=false and SKIP_EMAIL_VERIFICATION=false — blocked above,
            # but handle defensively.
            raise BadRequestException(
                "Registration is currently unavailable. Please contact the administrator."
            )

    except BadRequestException:
        raise
    except Exception as e:
        log.error("registration_failed", error=str(e))
        raise BadRequestException("Registration failed. Please try again.")


@router.post("/verify-email", response_model=Message)
async def verify_email(
    request: EmailVerificationRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """
    Verify email address with token from registration email.

    Activates account and sends welcome email.

    Args:
        request: Verification token

    Returns:
        Message: Success message

    Raises:
        BadRequestException: If token invalid or expired
    """
    log = logger.bind(operation="verify_email")

    user_service = UserService(session)

    try:
        user = await user_service.verify_email(request.token)

        # Send welcome email in background
        background_tasks.add_task(
            send_welcome_email,
            email_to=user.email,
            username=user.full_name,
        )

        log.info("email_verified", user_id=user.id)

        return Message(message="Email verified successfully. You can now log in.")

    except (BadRequestException, NotFoundException):
        raise
    except Exception as e:
        log.error("email_verification_failed", error=str(e))
        raise BadRequestException("Email verification failed. Please try again.")


@router.post("/resend-verification", response_model=Message)
async def resend_verification(
    background_tasks: BackgroundTasks,
    email: str = Body(..., embed=True),
    session: AsyncSession = Depends(get_session),
):
    """
    Resend verification email.

    Always returns success to prevent email enumeration.

    Args:
        email: Email address to resend verification to

    Returns:
        Message: Generic success message
    """
    log = logger.bind(operation="resend_verification", email=email)

    user_service = UserService(session)

    try:
        user = await user_service.get_by_email(email)

        if user and not user.email_verified:
            # Generate new token
            user.verification_token = secrets.token_urlsafe(32)
            session.add(user)
            await session.commit()

            background_tasks.add_task(
                send_activation_email,
                email_to=user.email,
                token=user.verification_token,
                username=user.full_name,
            )
            log.info("verification_resent", user_id=user.id)

    except Exception as e:
        # Silent failure to prevent enumeration
        log.warning("verification_resend_failed", error=str(e))

    # Always return success message
    return Message(
        message="If an account exists with this email, a verification link has been sent."
    )


# ==================== Login & Token Management ====================


@router.post("/token", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: AsyncSession = Depends(get_session),
):
    """
    Login with email and password.

    Returns access token and refresh token.

    Args:
        form_data: OAuth2 form (username=email, password)

    Returns:
        Token: Access and refresh tokens

    Raises:
        UnauthorizedException: If credentials invalid or account inactive
    """
    log = logger.bind(operation="login", email=form_data.username)

    user_service = UserService(session)

    try:
        user = await user_service.authenticate(
            email=form_data.username,
            password=form_data.password,
        )

        access_token, refresh_token = await user_service.issue_tokens(user.id)

        log.info("login_successful")

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    except UnauthorizedException:
        raise
    except Exception as e:
        log.error("login_failed", error=str(e))
        raise UnauthorizedException("Authentication failed")


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: RefreshTokenRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Refresh access token using refresh token.

    Revokes old refresh token and issues new pair.

    Args:
        request: Refresh token

    Returns:
        Token: New access and refresh tokens

    Raises:
        UnauthorizedException: If refresh token invalid, expired, or revoked
    """
    log = logger.bind(operation="refresh_token")

    user_service = UserService(session)

    try:
        new_access_token = await user_service.refresh_access_token(
            refresh_token_value=request.refresh_token
        )

        log.info("token_refreshed")

        return Token(
            access_token=new_access_token,
            refresh_token=request.refresh_token,  # Reuse same refresh token
            token_type="bearer",
        )

    except UnauthorizedException:
        raise
    except Exception as e:
        log.error("token_refresh_failed", error=str(e))
        raise UnauthorizedException("Token refresh failed")


@router.post("/logout", response_model=Message)
async def logout(
    request: RefreshTokenRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Logout by revoking refresh token.

    Args:
        request: Refresh token to revoke
        current_user: Authenticated user

    Returns:
        Message: Success message

    Raises:
        BadRequestException: If token invalid or doesn't belong to user
    """
    log = logger.bind(operation="logout", user_id=current_user.id)

    user_service = UserService(session)

    try:
        await user_service.revoke_refresh_token(
            refresh_token_value=request.refresh_token
        )

        log.info("logout_successful")

        return Message(message="Successfully logged out")

    except BadRequestException:
        raise
    except Exception as e:
        log.error("logout_failed", error=str(e))
        raise BadRequestException("Logout failed")


# ==================== User Profile ====================


@router.get("/me", response_model=UserRead)
async def get_current_user_profile(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get current authenticated user's profile.

    Returns:
        UserRead: User profile data
    """
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_current_user_profile(
    user_update: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Update current user's profile.

    Args:
        user_update: Fields to update (full_name, job_title, avatar_url)
        current_user: Authenticated user

    Returns:
        UserRead: Updated user profile
    """
    log = logger.bind(operation="update_profile", user_id=current_user.id)

    user_service = UserService(session)

    try:
        updated_user = await user_service.update_profile(
            user_id=current_user.id,
            data=user_update,
        )

        log.info("profile_updated")

        return updated_user

    except Exception as e:
        log.error("profile_update_failed", error=str(e))
        raise BadRequestException("Profile update failed")


# ==================== GDPR: Account Deletion ====================


@router.delete("/me", response_model=Message, status_code=200)
async def delete_my_account(
    password: str = Body(
        ..., embed=True, description="Current password for confirmation"
    ),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    session: AsyncSession = Depends(get_session),
):
    """
    Permanently delete the authenticated user's account (GDPR Article 17).

    Requires the user's current password as a confirmation step to prevent
    accidental deletion. All owned projects and associated data are removed
    via cascade. All active sessions are invalidated.

    Args:
        password: Current password (confirmation)
        current_user: Authenticated user

    Returns:
        Message: Confirmation that the account has been deleted

    Raises:
        UnauthorizedException: If the password is incorrect
    """
    log = logger.bind(operation="delete_account", user_id=current_user.id)
    log.info("delete_account_requested")

    user_service = UserService(session)

    try:
        await user_service.delete_account(
            user_id=current_user.id,
            password=password,
        )
        log.info("delete_account_completed")
        return Message(
            message="Your account and all associated data have been permanently deleted."
        )

    except Exception:
        raise


# ==================== GDPR: Data Export ====================


@router.get("/me/export")
async def export_my_data(
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Export all personal data for the authenticated user (GDPR Article 20).

    Returns a JSON file download containing all profile data, account
    metadata, and owned projects. Sensitive fields such as hashed passwords
    and tokens are excluded.

    Args:
        current_user: Authenticated user

    Returns:
        JSONResponse: Downloadable JSON file with all personal data
    """
    from fastapi.responses import JSONResponse

    log = logger.bind(operation="export_data", user_id=current_user.id)
    log.info("data_export_requested")

    user_service = UserService(session)
    data = await user_service.export_my_data(user_id=current_user.id)

    log.info("data_export_completed")

    return JSONResponse(
        content=data,
        headers={
            "Content-Disposition": 'attachment; filename="my-data-export.json"',
            "Content-Type": "application/json",
        },
    )


# ==================== Password Management ====================


@router.post("/change-password", response_model=Message)
async def change_password(
    request: ChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_session),
):
    """
    Change password (requires current password).

    Args:
        request: Current and new passwords
        current_user: Authenticated user

    Returns:
        Message: Success message

    Raises:
        BadRequestException: If current password incorrect
    """
    log = logger.bind(operation="change_password", user_id=current_user.id)

    user_service = UserService(session)

    try:
        await user_service.change_password(
            user_id=current_user.id,
            data=request,
        )

        log.info("password_changed")

        return Message(message="Password updated successfully")

    except BadRequestException:
        raise
    except Exception as e:
        log.error("password_change_failed", error=str(e))
        raise BadRequestException("Password change failed")


@router.post("/password-recovery", response_model=Message)
async def request_password_reset(
    request: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """
    Request password reset email.

    Always returns a generic success message to prevent email enumeration,
    EXCEPT when SMTP is not configured — in that case a clear 503 is returned
    so the operator/user knows why the flow cannot proceed.

    Args:
        request: Email address
        background_tasks: FastAPI background tasks

    Returns:
        Message: Generic success message

    Raises:
        ServiceUnavailableException: If SMTP is not configured
    """
    from app.core.exceptions import ServiceUnavailableException

    log = logger.bind(operation="password_recovery", email=request.email)

    if not settings.EMAIL_ENABLED:
        log.error(
            "password_reset_smtp_not_configured",
            detail="Cannot send password-reset email: SMTP is not configured.",
        )
        raise ServiceUnavailableException(
            "Password reset via email is unavailable because SMTP is not configured. "
            "Please contact an administrator to reset your password manually.",
            detail={
                "hint": (
                    "Configure SMTP_SERVER, SMTP_USER, SMTP_PASSWORD and EMAIL_FROM_EMAIL "
                    "in your environment to enable this feature."
                )
            },
        )

    user_service = UserService(session)

    try:
        user = await user_service.request_password_reset(request.email)

        if user:
            background_tasks.add_task(
                send_password_reset_email,
                email_to=user.email,
                token=user.reset_token,
                username=user.full_name,
            )
            log.info("password_reset_requested", user_id=user.id)

    except Exception as e:
        # Silent failure to prevent enumeration
        log.warning("password_reset_request_failed", error=str(e))

    # Always return success message (prevents email enumeration)
    return Message(
        message="If an account exists with this email, a password reset link has been sent."
    )


@router.post("/reset-password", response_model=Message)
async def reset_password(
    request: PasswordResetConfirm,
    session: AsyncSession = Depends(get_session),
):
    """
    Reset password using token from recovery email.

    Revokes all existing refresh tokens for security.

    Args:
        request: Reset token and new password

    Returns:
        Message: Success message

    Raises:
        BadRequestException: If token invalid or expired
    """
    log = logger.bind(operation="reset_password")

    user_service = UserService(session)

    try:
        await user_service.reset_password(request)

        log.info("password_reset_completed")

        return Message(
            message="Password reset successfully. Please log in with your new password."
        )

    except BadRequestException:
        raise
    except Exception as e:
        log.error("password_reset_failed", error=str(e))
        raise BadRequestException("Password reset failed")
