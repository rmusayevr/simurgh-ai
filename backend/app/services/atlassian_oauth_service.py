"""
Atlassian OAuth service.

Handles the OAuth 2.0 (3LO) authorization code flow for Atlassian login,
covering both Jira and Confluence access.

Flow:
    1. User clicks "Continue with Atlassian" → redirected to Atlassian
    2. User approves → redirected back with ?code=...
    3. Frontend POSTs code to /auth/atlassian/callback
    4. We exchange code for access + refresh tokens
    5. We fetch accessible resources to get cloud_id + site_url
    6. Tokens are encrypted with Fernet and stored in atlassian_credentials
    7. Future Jira/Confluence API calls use stored tokens automatically

Token refresh:
    Access tokens expire after ~1 hour. The service proactively refreshes
    them before they expire. A Celery beat task runs every 30 minutes to
    refresh credentials expiring within the next hour.
"""

import httpx
import structlog
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.core.encryption import encrypt_token, decrypt_token
from app.models.user import User, UserRole
from app.models.token import RefreshToken
from app.models.atlassian_credential import AtlassianCredential
from app.core.exceptions import BadRequestException

logger = structlog.get_logger(__name__)

ATLASSIAN_AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
ATLASSIAN_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
ATLASSIAN_USERINFO_URL = "https://api.atlassian.com/me"
ATLASSIAN_ACCESSIBLE_RESOURCES_URL = (
    "https://api.atlassian.com/oauth/token/accessible-resources"
)

# Scopes registered in the Atlassian developer console
ATLASSIAN_SCOPES = [
    # User identity (classic)
    "read:me",
    # Jira classic scopes
    "read:jira-work",
    "read:jira-user",
    "write:jira-work",
    # Jira granular scopes
    "read:issue:jira",
    "write:issue:jira",
    "read:issue-details:jira",
    "read:user:jira",
    "read:project:jira",
    # Confluence classic scopes
    "read:confluence-content.all",
    "read:confluence-space.summary",
    "write:confluence-content",
    # Confluence granular scopes
    "read:content:confluence",
    "write:content:confluence",
    "read:space-details:confluence",
    # Required for refresh tokens
    "offline_access",
]


class AtlassianOAuthService:
    """Manages the Atlassian OAuth 2.0 (3LO) flow and credential storage."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Step 1: Authorization URL ─────────────────────────────────────────────

    def get_authorization_url(self, state: str) -> str:
        """
        Build the Atlassian OAuth authorization URL.

        Args:
            state: CSRF state token

        Returns:
            str: Full Atlassian authorization URL
        """
        if not settings.ATLASSIAN_CLIENT_ID:
            raise BadRequestException(
                "Atlassian OAuth is not configured on this server."
            )

        scope_str = "%20".join(ATLASSIAN_SCOPES)
        params = (
            f"audience=api.atlassian.com"
            f"&client_id={settings.ATLASSIAN_CLIENT_ID}"
            f"&scope={scope_str}"
            f"&redirect_uri={settings.FRONTEND_URL}/auth/atlassian/callback"
            f"&state={state}"
            f"&response_type=code"
            f"&prompt=consent"
        )
        return f"{ATLASSIAN_AUTHORIZE_URL}?{params}"

    # ── Step 2: Exchange code for tokens ─────────────────────────────────────

    async def exchange_code(self, code: str) -> dict:
        """
        Exchange the authorization code for Atlassian access + refresh tokens.

        Also fetches:
            - User identity from /me endpoint
            - Accessible Atlassian sites (cloud_id, site_url) from
              /accessible-resources

        Args:
            code: Authorization code from Atlassian callback

        Returns:
            dict with keys: access_token, refresh_token, expires_in,
                            user_profile, cloud_id, site_url, site_name, scopes

        Raises:
            BadRequestException: If exchange fails or no accessible sites found
        """
        if not settings.ATLASSIAN_CLIENT_ID or not settings.ATLASSIAN_CLIENT_SECRET:
            raise BadRequestException(
                "Atlassian OAuth is not configured on this server."
            )

        async with httpx.AsyncClient(timeout=15.0) as client:
            # Exchange code for tokens
            token_res = await client.post(
                ATLASSIAN_TOKEN_URL,
                json={
                    "grant_type": "authorization_code",
                    "client_id": settings.ATLASSIAN_CLIENT_ID,
                    "client_secret": settings.ATLASSIAN_CLIENT_SECRET.get_secret_value(),
                    "code": code,
                    "redirect_uri": f"{settings.FRONTEND_URL}/auth/atlassian/callback",
                },
                headers={"Content-Type": "application/json"},
            )

            token_data = token_res.json()
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 3600)  # seconds, default 1hr

            if not access_token:
                logger.warning("atlassian_token_exchange_failed", response=token_data)
                raise BadRequestException(
                    "Atlassian authorization failed. Please try again."
                )

            auth_headers = {"Authorization": f"Bearer {access_token}"}

            # Fetch user identity
            me_res = await client.get(ATLASSIAN_USERINFO_URL, headers=auth_headers)
            user_profile = me_res.json()

            if "account_id" not in user_profile:
                logger.warning("atlassian_userinfo_failed", response=user_profile)
                raise BadRequestException(
                    "Failed to fetch Atlassian profile. Please try again."
                )

            # Fetch accessible Atlassian sites
            resources_res = await client.get(
                ATLASSIAN_ACCESSIBLE_RESOURCES_URL,
                headers=auth_headers,
            )
            resources = resources_res.json()

            if not resources:
                raise BadRequestException(
                    "No accessible Atlassian sites found. "
                    "Make sure you have access to at least one Jira or Confluence site."
                )

            # Use the first site — most users have only one
            site = resources[0]

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": expires_in,
                "user_profile": user_profile,
                "cloud_id": site["id"],
                "site_url": site["url"],
                "site_name": site.get("name", ""),
                "scopes": token_data.get("scope", ""),
            }

    # ── Step 3: Find or create Simurgh user ──────────────────────────────────

    async def get_or_create_user(self, exchange_data: dict) -> User:
        """
        Find or create a Simurgh user from the Atlassian profile.

        Also saves/updates the AtlassianCredential with encrypted tokens.

        Args:
            exchange_data: Full dict returned by exchange_code()

        Returns:
            User: Activated user ready for Simurgh token issuance
        """
        user_profile = exchange_data["user_profile"]
        atlassian_id = user_profile["account_id"]
        email = (user_profile.get("email") or "").lower()
        name = user_profile.get("name") or (
            email.split("@")[0] if email else "Atlassian User"
        )
        avatar_url = user_profile.get("picture")

        if not email:
            raise BadRequestException(
                "Your Atlassian account has no email address. "
                "Please ensure your Atlassian profile has a verified email."
            )

        # 1. Existing Atlassian-linked account
        result = await self.db.exec(
            select(User).where(User.atlassian_id == atlassian_id)
        )
        user = result.first()

        if not user:
            # 2. Existing email account — link Atlassian identity
            result = await self.db.exec(select(User).where(User.email == email))
            user = result.first()

            if user:
                user.atlassian_id = atlassian_id
                if not user.oauth_provider:
                    user.oauth_provider = "atlassian"
                if avatar_url and not user.avatar_url:
                    user.avatar_url = avatar_url
                if not user.email_verified:
                    user.verify_email()
                logger.info("atlassian_oauth_linked_existing", user_id=user.id)

        if not user:
            # 3. Brand new user
            user = User(
                email=email,
                hashed_password="",
                full_name=name,
                atlassian_id=atlassian_id,
                oauth_provider="atlassian",
                avatar_url=avatar_url,
                is_active=True,
                email_verified=True,
                role=UserRole.USER,
                terms_accepted=True,
                terms_accepted_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            self.db.add(user)
            await self.db.flush()  # Get user.id before saving credential
            logger.info("atlassian_oauth_new_user", email=email)
        else:
            if avatar_url and not user.avatar_url:
                user.avatar_url = avatar_url

        user.update_last_login()
        self.db.add(user)
        await self.db.flush()

        # Save / update the encrypted credential
        await self._upsert_credential(user.id, exchange_data)

        await self.db.commit()
        await self.db.refresh(user)
        return user

    # ── Step 4: Issue Simurgh JWT tokens ─────────────────────────────────────

    async def issue_tokens(self, user: User) -> tuple[str, str]:
        """Issue Simurgh access + refresh tokens."""
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

    # ── Credential helpers ────────────────────────────────────────────────────

    async def _upsert_credential(
        self, user_id: int, exchange_data: dict
    ) -> AtlassianCredential:
        """
        Insert or update the AtlassianCredential for a user.

        Tokens are Fernet-encrypted before writing to DB.
        """
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            seconds=exchange_data["expires_in"]
        )

        result = await self.db.exec(
            select(AtlassianCredential).where(AtlassianCredential.user_id == user_id)
        )
        cred = result.first()

        if cred:
            cred.cloud_id = exchange_data["cloud_id"]
            cred.site_url = exchange_data["site_url"]
            cred.site_name = exchange_data["site_name"]
            cred.access_token_enc = encrypt_token(exchange_data["access_token"])
            cred.refresh_token_enc = encrypt_token(exchange_data["refresh_token"])
            cred.token_expires_at = expires_at
            cred.scopes = exchange_data["scopes"]
            cred.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            cred = AtlassianCredential(
                user_id=user_id,
                cloud_id=exchange_data["cloud_id"],
                site_url=exchange_data["site_url"],
                site_name=exchange_data["site_name"],
                access_token_enc=encrypt_token(exchange_data["access_token"]),
                refresh_token_enc=encrypt_token(exchange_data["refresh_token"]),
                token_expires_at=expires_at,
                scopes=exchange_data["scopes"],
            )

        self.db.add(cred)
        return cred

    async def get_valid_access_token(self, user_id: int) -> Optional[str]:
        """
        Return a valid Atlassian access token for a user, refreshing if needed.

        Called by Jira/Confluence service methods before making API calls.

        Args:
            user_id: Simurgh user ID

        Returns:
            str: Valid access token, or None if no credential stored
        """
        result = await self.db.exec(
            select(AtlassianCredential).where(AtlassianCredential.user_id == user_id)
        )
        cred = result.first()

        if not cred:
            return None

        # Refresh if expiring within the next 5 minutes
        buffer = timedelta(minutes=5)
        if (
            datetime.now(timezone.utc).replace(tzinfo=None) + buffer
            >= cred.token_expires_at
        ):
            cred = await self._refresh_credential(cred)
            if not cred:
                return None

        return decrypt_token(cred.access_token_enc)

    async def _refresh_credential(
        self, cred: AtlassianCredential
    ) -> Optional[AtlassianCredential]:
        """
        Use the stored refresh token to get a new access token from Atlassian.

        Updates the credential in place if successful.
        Returns None if refresh fails (user must re-authenticate).
        """
        if not settings.ATLASSIAN_CLIENT_ID or not settings.ATLASSIAN_CLIENT_SECRET:
            return None

        try:
            refresh_token = decrypt_token(cred.refresh_token_enc)

            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    ATLASSIAN_TOKEN_URL,
                    json={
                        "grant_type": "refresh_token",
                        "client_id": settings.ATLASSIAN_CLIENT_ID,
                        "client_secret": settings.ATLASSIAN_CLIENT_SECRET.get_secret_value(),
                        "refresh_token": refresh_token,
                    },
                    headers={"Content-Type": "application/json"},
                )

                token_data = res.json()
                new_access_token = token_data.get("access_token")
                new_refresh_token = token_data.get("refresh_token", refresh_token)
                expires_in = token_data.get("expires_in", 3600)

                if not new_access_token:
                    logger.warning(
                        "atlassian_token_refresh_failed",
                        user_id=cred.user_id,
                        response=token_data,
                    )
                    return None

            cred.access_token_enc = encrypt_token(new_access_token)
            cred.refresh_token_enc = encrypt_token(new_refresh_token)
            cred.token_expires_at = datetime.now(timezone.utc).replace(
                tzinfo=None
            ) + timedelta(seconds=expires_in)
            cred.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

            self.db.add(cred)
            await self.db.commit()
            await self.db.refresh(cred)

            logger.info("atlassian_token_refreshed", user_id=cred.user_id)
            return cred

        except Exception as e:
            logger.error(
                "atlassian_token_refresh_error", user_id=cred.user_id, error=str(e)
            )
            return None

    async def get_credential(self, user_id: int) -> Optional[AtlassianCredential]:
        """Return the raw credential row for a user (for display in Settings)."""
        result = await self.db.exec(
            select(AtlassianCredential).where(AtlassianCredential.user_id == user_id)
        )
        return result.first()

    async def disconnect(self, user_id: int) -> None:
        """Remove stored Atlassian credential and unlink atlassian_id from user."""
        result = await self.db.exec(
            select(AtlassianCredential).where(AtlassianCredential.user_id == user_id)
        )
        cred = result.first()
        if cred:
            await self.db.delete(cred)

        user = await self.db.get(User, user_id)
        if user:
            user.atlassian_id = None
            if user.oauth_provider == "atlassian":
                user.oauth_provider = None
            self.db.add(user)

        await self.db.commit()
        logger.info("atlassian_credential_disconnected", user_id=user_id)
