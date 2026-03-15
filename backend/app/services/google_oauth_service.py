"""
Google OAuth service.

Handles the OAuth 2.0 authorization code flow for Google login:
    - Generating the authorization URL
    - Exchanging the authorization code for a Google access token
    - Fetching the Google user profile via the userinfo endpoint
    - Creating or linking a Simurgh user account

Google's userinfo endpoint returns a verified email directly —
no secondary call needed unlike GitHub.
"""

import httpx
import structlog
from datetime import datetime, timezone, timedelta

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.models.user import User, UserRole
from app.models.token import RefreshToken
from app.core.exceptions import BadRequestException

logger = structlog.get_logger(__name__)

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleOAuthService:
    """Manages the Google OAuth 2.0 flow and user account linking."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Step 1: Build the authorization URL ───────────────────────────────────

    def get_authorization_url(self, state: str) -> str:
        """
        Build the Google OAuth authorization URL.

        Args:
            state: CSRF state token

        Returns:
            str: Full Google authorization URL to redirect the user to
        """
        if not settings.GOOGLE_CLIENT_ID:
            raise BadRequestException("Google OAuth is not configured on this server.")

        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": f"{settings.FRONTEND_URL}/auth/google/callback",
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{GOOGLE_AUTHORIZE_URL}?{query}"

    # ── Step 2: Exchange code → Google token → user profile ───────────────────

    async def exchange_code(self, code: str) -> dict:
        """
        Exchange the OAuth authorization code for a Google access token,
        then fetch the user profile from the userinfo endpoint.

        Google's userinfo endpoint always returns a verified email (Google
        enforces verification on all accounts), so no secondary email
        lookup is needed.

        Args:
            code: Authorization code from Google callback

        Returns:
            dict: Google user profile with 'sub', 'email', 'name', 'picture'

        Raises:
            BadRequestException: If exchange fails or profile fetch fails
        """
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise BadRequestException("Google OAuth is not configured on this server.")

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Exchange code for tokens
            token_res = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET.get_secret_value(),
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": f"{settings.FRONTEND_URL}/auth/google/callback",
                },
                headers={"Accept": "application/json"},
            )

            token_data = token_res.json()
            access_token = token_data.get("access_token")

            if not access_token:
                logger.warning("google_token_exchange_failed", response=token_data)
                raise BadRequestException(
                    "Google authorization failed. Please try again."
                )

            # Fetch user profile from userinfo endpoint
            profile_res = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            profile = profile_res.json()

            if "error" in profile:
                logger.warning("google_userinfo_failed", response=profile)
                raise BadRequestException(
                    "Failed to fetch Google profile. Please try again."
                )

            email = profile.get("email")
            email_verified = profile.get("email_verified", False)

            if not email:
                raise BadRequestException("Your Google account has no email address.")

            if not email_verified:
                raise BadRequestException(
                    "Your Google account email is not verified. "
                    "Please verify your Google account first."
                )

            return profile

    # ── Step 3: Find or create Simurgh user ───────────────────────────────────

    async def get_or_create_user(self, google_profile: dict) -> User:
        """
        Find an existing user linked to this Google account, or create one.

        Logic:
            1. Match by google_id (returning user)
            2. Match by email (existing password-auth or GitHub user — link accounts)
            3. Create a brand new user

        Args:
            google_profile: Google userinfo profile from exchange_code()

        Returns:
            User: Activated, verified user ready for token issuance
        """
        google_id = str(google_profile["sub"])
        email = google_profile["email"].lower()
        name = google_profile.get("name") or email.split("@")[0]
        avatar_url = google_profile.get("picture")

        # 1. Existing Google-linked account
        result = await self.db.exec(select(User).where(User.google_id == google_id))
        user = result.first()

        if user:
            if avatar_url and not user.avatar_url:
                user.avatar_url = avatar_url
            user.update_last_login()
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            logger.info("google_oauth_existing_user", user_id=user.id)
            return user

        # 2. Existing email account — link Google identity
        result = await self.db.exec(select(User).where(User.email == email))
        user = result.first()

        if user:
            user.google_id = google_id
            # Only overwrite oauth_provider if account has no existing provider
            if not user.oauth_provider:
                user.oauth_provider = "google"
            if avatar_url and not user.avatar_url:
                user.avatar_url = avatar_url
            if not user.email_verified:
                user.verify_email()
            user.update_last_login()
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            logger.info("google_oauth_linked_existing", user_id=user.id)
            return user

        # 3. New user
        user = User(
            email=email,
            hashed_password="",
            full_name=name,
            google_id=google_id,
            oauth_provider="google",
            avatar_url=avatar_url,
            is_active=True,
            email_verified=True,
            role=UserRole.USER,
            terms_accepted=True,
            terms_accepted_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        logger.info("google_oauth_new_user", user_id=user.id, email=email)
        return user

    # ── Step 4: Issue Simurgh JWT tokens ──────────────────────────────────────

    async def issue_tokens(self, user: User) -> tuple[str, str]:
        """
        Issue a Simurgh access + refresh token pair.

        Returns:
            tuple[str, str]: (access_token, refresh_token)
        """
        access_token = create_access_token(subject=str(user.id))
        refresh_token_value = create_refresh_token(subject=str(user.id))

        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        refresh_token = RefreshToken(
            user_id=user.id,
            token=refresh_token_value,
            expires_at=expires_at,
        )
        self.db.add(refresh_token)
        await self.db.commit()

        return access_token, refresh_token_value
