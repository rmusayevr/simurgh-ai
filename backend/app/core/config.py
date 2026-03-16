"""
Application configuration management.

Loads settings from environment variables with validation and type safety.
Uses Pydantic for automatic validation and type coercion.
"""

from typing import List, Union, Optional

from pydantic import field_validator, EmailStr, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Configuration is loaded from:
        1. Environment variables
        2. .env file (if present)
        3. Default values (where specified)

    All settings are immutable after initialization.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore unknown env vars
    )

    # ==================== Project Metadata ====================
    PROJECT_NAME: str = "Simurgh AI"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = True
    EXPOSE_DOCS: bool = (
        False  # Set to true only in local dev; never in staging or production
    )

    # ==================== Frontend Configuration ====================
    FRONTEND_URL: str = "http://localhost:5173"
    """Frontend URL for CORS and email links (e.g., password reset)"""

    # ==================== Security ====================
    SECRET_KEY: SecretStr
    """Secret key for JWT signing - MUST be set in environment"""

    ENCRYPTION_KEY: SecretStr
    """32-byte URL-safe base64-encoded key for sensitive data encryption"""

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PASSWORD_RESET_EXPIRE_HOURS: int = 1

    ALGORITHM: str = "HS256"
    """JWT signing algorithm"""

    # ==================== Database ====================
    DATABASE_URL: str
    """PostgreSQL connection string (auto-converted to asyncpg)"""

    DATABASE_POOL_SIZE: int = 5
    """Connection pool size for database"""

    DATABASE_MAX_OVERFLOW: int = 10
    """Maximum overflow connections beyond pool size"""

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """
        Auto-corrects PostgreSQL URL scheme for asyncpg driver.

        Converts:
            postgres://... → postgresql+asyncpg://...
            postgresql://... → postgresql+asyncpg://...
        """
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # ==================== Redis / Caching ====================
    REDIS_URL: str = "redis://redis:6379/0"
    """Redis connection URL for caching and Celery broker"""

    CACHE_TTL_SECONDS: int = 300  # 5 minutes
    """Default cache TTL for Redis"""

    # ==================== AI / LLM Configuration ====================
    ANTHROPIC_API_KEY: SecretStr
    """Anthropic API key for Claude access"""

    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    """Default Claude model for AI operations"""

    ANTHROPIC_MAX_TOKENS: int = 4096
    """Default max tokens for Claude responses"""

    ANTHROPIC_TEMPERATURE: float = 0.7
    """Default temperature for AI responses (0.0 = deterministic, 1.0 = creative)"""

    @field_validator("EMBEDDING_DIMENSIONS")
    @classmethod
    def validate_embedding_dimensions(cls, v: int, values) -> int:
        """
        Guard against EMBEDDING_DIMENSIONS drifting out of sync with EMBEDDING_MODEL.

        Known FastEmbed model → dimension mappings:
            BAAI/bge-small-en-v1.5 → 384
            BAAI/bge-base-en-v1.5  → 768
            BAAI/bge-large-en-v1.5 → 1024

        The DocumentChunk.embedding column and the pgvector HNSW index are both
        created with Vector(384).  If EMBEDDING_DIMENSIONS doesn't match the actual
        model output, stored vectors will be the wrong length and cosine-similarity
        queries will fail or silently return garbage.
        """
        known = {
            "BAAI/bge-small-en-v1.5": 384,
            "BAAI/bge-base-en-v1.5": 768,
            "BAAI/bge-large-en-v1.5": 1024,
        }
        model = values.data.get("EMBEDDING_MODEL", "")
        expected = known.get(model)
        if expected is not None and v != expected:
            raise ValueError(
                f"EMBEDDING_DIMENSIONS={v} does not match {model} "
                f"(expected {expected}). Update EMBEDDING_DIMENSIONS or "
                f"create a new Alembic migration to resize the vector column."
            )
        return v

    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    """FastEmbed model for RAG. Must match EMBEDDING_DIMENSIONS below.
    BAAI/bge-small-en-v1.5 → 384 dims
    BAAI/bge-base-en-v1.5  → 768 dims
    text-embedding-ada-002 → 1536 dims  (OpenAI, not used here)
    """

    EMBEDDING_DIMENSIONS: int = 384
    """Vector dimensions produced by EMBEDDING_MODEL.
    CRITICAL: This must match Vector(N) in DocumentChunk.embedding and the
    pgvector HNSW index (idx_chunk_embedding). Changing it requires a new
    Alembic migration to drop/recreate the column and index.
    BAAI/bge-small-en-v1.5 → 384 (correct default).
    """

    CHUNK_SIZE: int = 500
    """Document chunk size for RAG (in tokens)"""

    CHUNK_OVERLAP: int = 50
    """Overlap between document chunks"""

    # ==================== Email ====================
    # Primary: Resend SDK (recommended — bypasses SMTP port blocks)
    RESEND_API_KEY: Optional[SecretStr] = None
    """Resend API key (re_...). Get one at resend.com. Takes priority over SMTP when set."""

    # Fallback: raw SMTP
    SMTP_SERVER: Optional[str] = None
    SMTP_PORT: int = 587
    """SMTP port. 587 = STARTTLS (default). 465 = implicit SSL (often blocked by hosting providers)."""
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[SecretStr] = None
    SMTP_TLS: bool = False
    """Override: implicit SSL. Auto-set per port. Only needed for non-standard ports."""
    SMTP_STARTTLS: bool = True
    """Override: STARTTLS. Auto-set per port. Only needed for non-standard ports."""

    EMAIL_FROM_EMAIL: Optional[EmailStr] = None
    EMAIL_FROM_NAME: str = "Simurgh AI"

    # Email feature flags
    EMAIL_ENABLED: bool = False
    """Master switch — auto-enabled when Resend key or full SMTP config is present."""

    @field_validator("EMAIL_ENABLED", mode="before")
    @classmethod
    def check_email_config(cls, v: bool, values) -> bool:
        """Auto-enable email if Resend or SMTP is fully configured."""
        if v:
            return v
        resend_configured = bool(values.data.get("RESEND_API_KEY"))
        smtp_configured = all(
            [
                values.data.get("SMTP_SERVER"),
                values.data.get("SMTP_USER"),
                values.data.get("SMTP_PASSWORD"),
                values.data.get("EMAIL_FROM_EMAIL"),
            ]
        )
        return resend_configured or smtp_configured

    # ==================== CORS ====================
    BACKEND_CORS_ORIGINS: List[str] = []
    """Allowed CORS origins for API access"""

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("["):
                import json

                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return []

    # ==================== File Storage ====================
    MAX_UPLOAD_SIZE_MB: int = 50
    """Maximum file upload size in megabytes"""

    ALLOWED_UPLOAD_EXTENSIONS: List[str] = [".pdf", ".docx", ".txt", ".md"]
    """Allowed file extensions for document upload"""

    UPLOAD_DIR: str = "/tmp/uploads"
    """Temporary directory for file uploads"""

    # ==================== Celery / Background Tasks ====================
    CELERY_BROKER_URL: Optional[str] = None
    """Celery broker URL (defaults to REDIS_URL if not set)"""

    CELERY_RESULT_BACKEND: Optional[str] = None
    """Celery result backend (defaults to REDIS_URL if not set)"""

    @field_validator("CELERY_BROKER_URL", mode="before")
    @classmethod
    def default_celery_broker(cls, v: Optional[str], values) -> str:
        """Use Redis URL as Celery broker if not explicitly set."""
        return v or values.data.get("REDIS_URL", "redis://redis:6379/0")

    @field_validator("CELERY_RESULT_BACKEND", mode="before")
    @classmethod
    def default_celery_backend(cls, v: Optional[str], values) -> str:
        """Use Redis URL as Celery result backend if not explicitly set."""
        return v or values.data.get("REDIS_URL", "redis://redis:6379/0")

    # ==================== GitHub OAuth ====================
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[SecretStr] = None

    # ==================== Google OAuth ====================
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[SecretStr] = None

    # ==================== Atlassian OAuth ====================
    ATLASSIAN_CLIENT_ID: Optional[str] = None
    ATLASSIAN_CLIENT_SECRET: Optional[SecretStr] = None

    # ==================== Rate Limiting ====================
    RATE_LIMIT_ENABLED: bool = True
    """Enable API rate limiting"""

    RATE_LIMIT_PER_MINUTE: int = 200
    """Maximum API requests per minute per authenticated user.
    200 rpm gives ~3 req/s sustained headroom for a React SPA.
    The proposal poller fires every 5 s (12 rpm), leaving 188 rpm
    for normal navigation, page loads, and API calls.
    """

    RATE_LIMIT_AUTH_PER_MINUTE: int = 20
    """
    Maximum requests per minute to auth endpoints (/auth/token, /auth/refresh)
    per IP address.  These endpoints never carry a Bearer token so they always
    fall into the IP bucket.  20 rpm is generous for legitimate use (proactive
    refresh fires at most once per 30 s) while still blocking brute-force.
    Kept separate from the general anonymous IP limit so a burst of page-load
    requests cannot exhaust the login/refresh allowance, and vice-versa.
    """

    RATE_LIMIT_ANONYMOUS_PER_MINUTE: int = 30
    """Maximum requests per minute for anonymous (non-auth, no Bearer token) IP traffic."""

    # ==================== Logging ====================
    LOG_LEVEL: str = "INFO"
    """Logging level (DEBUG | INFO | WARNING | ERROR | CRITICAL)"""

    LOG_FORMAT: str = "json"
    """Log output format (json | text)"""

    # ==================== Feature Flags ====================
    MAINTENANCE_MODE: bool = False
    """Enable maintenance mode (blocks all API requests)"""

    ENABLE_DEBATE_FEATURE: bool = True
    """Enable multi-agent debate feature"""

    ENABLE_RAG: bool = True
    """Enable RAG document processing"""

    # ==================== Thesis Evaluation Mode ====================
    THESIS_MODE: bool = False
    """Enable thesis evaluation features (A/B testing, questionnaires)"""

    EXPERIMENT_SESSION_TIMEOUT_MINUTES: int = 60
    """Timeout for experiment sessions"""

    SKIP_EMAIL_VERIFICATION: bool = False
    """Skip email verification step for user registration (for testing)"""

    # ==================== Helper Properties ====================

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT.lower() == "development"

    @property
    def resend_configured(self) -> bool:
        """Resend SDK is ready — API key + from-address present."""
        return bool(self.RESEND_API_KEY and self.EMAIL_FROM_EMAIL)

    @property
    def smtp_configured(self) -> bool:
        """SMTP fallback is fully configured."""
        return all(
            [
                self.SMTP_SERVER,
                self.SMTP_USER,
                self.SMTP_PASSWORD,
                self.EMAIL_FROM_EMAIL,
            ]
        )


# Singleton instance
settings = Settings()


# Validation on import
if __name__ != "__main__":
    # Validate critical settings
    assert settings.SECRET_KEY, "SECRET_KEY must be set in environment"
    assert settings.DATABASE_URL, "DATABASE_URL must be set in environment"
    assert settings.ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY must be set in environment"
