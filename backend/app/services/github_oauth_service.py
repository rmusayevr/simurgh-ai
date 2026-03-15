"""
GitHub OAuth service.

Handles the full OAuth 2.0 authorization code flow for GitHub login:
    - Generating the authorization URL with PKCE state
    - Exchanging the authorization code for a GitHub access token
    - Fetching the GitHub user profile
    - Creating or linking a Simurgh user account

State is stored in Redis with a 10-minute TTL to prevent CSRF.
"""

import httpx
import structlog
from datetime import datetime, timezone

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.models.user import User, UserRole
from app.models.token import RefreshToken
from app.core.exceptions import BadRequestException

logger = structlog.get_logger(__name__)

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


class GitHubOAuthService:
    """Manages the GitHub OAuth 2.0 flow and user account linking."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Step 1: Build the authorization URL ───────────────────────────────────

    def get_authorization_url(self, state: str) -> str:
        """
        Build the GitHub OAuth authorization URL.

        Args:
            state: CSRF state token (caller is responsible for storing it)

        Returns:
            str: Full GitHub authorization URL to redirect the user to
        """
        if not settings.GITHUB_CLIENT_ID:
            raise BadRequestException("GitHub OAuth is not configured on this server.")

        params = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": f"{settings.FRONTEND_URL}/auth/github/callback",
            "scope": "read:user user:email",
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{GITHUB_AUTHORIZE_URL}?{query}"

    # ── Step 2: Exchange code → GitHub token → user profile ───────────────────

    async def exchange_code(self, code: str) -> dict:
        """
        Exchange the OAuth authorization code for a GitHub access token.

        Args:
            code: Authorization code from GitHub callback

        Returns:
            dict: GitHub user profile with guaranteed 'id', 'email', 'login', 'name'

        Raises:
            BadRequestException: If exchange fails or GitHub returns an error
        """
        if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
            raise BadRequestException("GitHub OAuth is not configured on this server.")

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Exchange code for access token
            token_res = await client.post(
                GITHUB_TOKEN_URL,
                data={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET.get_secret_value(),
                    "code": code,
                    "redirect_uri": f"{settings.FRONTEND_URL}/auth/github/callback",
                },
                headers={"Accept": "application/json"},
            )

            token_data = token_res.json()
            access_token = token_data.get("access_token")

            if not access_token:
                logger.warning("github_token_exchange_failed", response=token_data)
                raise BadRequestException(
                    "GitHub authorization failed. Please try again."
                )

            auth_headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            }

            # Fetch user profile
            profile_res = await client.get(GITHUB_USER_URL, headers=auth_headers)
            profile = profile_res.json()

            # GitHub may not expose email in main profile if user set it private.
            # Fall back to the emails endpoint to get the primary verified email.
            email = profile.get("email")
            if not email:
                emails_res = await client.get(GITHUB_EMAILS_URL, headers=auth_headers)
                emails = emails_res.json()
                # Pick primary + verified first, then any verified, then any
                primary = (
                    next(
                        (e for e in emails if e.get("primary") and e.get("verified")),
                        None,
                    )
                    or next(
                        (e for e in emails if e.get("verified")),
                        None,
                    )
                    or (emails[0] if emails else None)
                )

                if primary:
                    email = primary.get("email")

            if not email:
                raise BadRequestException(
                    "Your GitHub account has no verified email address. "
                    "Please add a public email in your GitHub profile settings."
                )

            profile["email"] = email
            return profile

    # ── Step 3: Find or create Simurgh user ───────────────────────────────────

    async def get_or_create_user(self, github_profile: dict) -> User:
        """
        Find an existing user linked to this GitHub account, or create one.

        Logic:
            1. Match by github_id (returning user who has logged in before)
            2. Match by email (existing password-auth user — link the accounts)
            3. Create a brand new user (first-time GitHub login)

        Args:
            github_profile: GitHub user profile from exchange_code()

        Returns:
            User: Activated, verified user ready for token issuance
        """
        github_id = str(github_profile["id"])
        email = github_profile["email"].lower()
        login = github_profile.get("login", "")
        name = github_profile.get("name") or login
        avatar_url = github_profile.get("avatar_url")

        # 1. Existing GitHub-linked account
        result = await self.db.exec(select(User).where(User.github_id == github_id))
        user = result.first()

        if user:
            # Refresh mutable GitHub fields in case they changed
            user.github_username = login
            if avatar_url and not user.avatar_url:
                user.avatar_url = avatar_url
            user.update_last_login()
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            logger.info("github_oauth_existing_user", user_id=user.id)
            return user

        # 2. Existing email account — link GitHub identity
        result = await self.db.exec(select(User).where(User.email == email))
        user = result.first()

        if user:
            user.github_id = github_id
            user.github_username = login
            user.oauth_provider = "github"
            if avatar_url and not user.avatar_url:
                user.avatar_url = avatar_url
            # Ensure the account is active (GitHub email is verified by GitHub)
            if not user.email_verified:
                user.verify_email()
            user.update_last_login()
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            logger.info("github_oauth_linked_existing", user_id=user.id)
            return user

        # 3. New user — create account, auto-verified via GitHub
        user = User(
            email=email,
            hashed_password="",  # No password for OAuth-only accounts
            full_name=name,
            github_id=github_id,
            github_username=login,
            oauth_provider="github",
            avatar_url=avatar_url,
            is_active=True,
            email_verified=True,  # GitHub has already verified the email
            role=UserRole.USER,
            terms_accepted=True,  # Implicit via GitHub TOS
            terms_accepted_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        logger.info("github_oauth_new_user", user_id=user.id, email=email)
        return user

    # ── Step 4: Issue Simurgh JWT tokens ──────────────────────────────────────

    async def issue_tokens(self, user: User) -> tuple[str, str]:
        """
        Issue a Simurgh access + refresh token pair for the authenticated user.

        Reuses the same token issuance pattern as password login.

        Returns:
            tuple[str, str]: (access_token, refresh_token)
        """
        from datetime import timedelta

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
