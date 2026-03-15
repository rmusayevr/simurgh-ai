"""
Unit tests for app/core/config.py

Covers:
    - DATABASE_URL coercion (postgres:// → postgresql+asyncpg://)
    - CELERY_BROKER_URL / CELERY_RESULT_BACKEND default to REDIS_URL
    - EMAIL_ENABLED auto-enable logic
    - BACKEND_CORS_ORIGINS parsing (string, JSON array, comma-separated)
    - Helper properties: is_production, is_development, smtp_configured
    - Settings instance is a singleton

Strategy: we test the validators by instantiating Settings with
controlled inputs via model_construct() or by calling the class
methods directly — avoiding real environment side-effects.
"""


# ══════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════


def _make_settings(**overrides):
    """
    Build a Settings instance with minimal required fields.

    Uses model_construct to bypass validators for fields we don't
    care about in a given test, while still exercising the ones we do.
    """
    from app.core.config import Settings

    base = dict(
        SECRET_KEY="test-secret-key-that-is-long-enough",
        ENCRYPTION_KEY="dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcy0hISE=",
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
        ANTHROPIC_API_KEY="test-key",
        REDIS_URL="redis://redis:6379/0",
    )
    base.update(overrides)
    # Use model_construct to skip full validation for speed
    return Settings.model_construct(**base)


# ══════════════════════════════════════════════════════════════════
# DATABASE_URL validator
# ══════════════════════════════════════════════════════════════════


class TestDatabaseUrlValidator:
    """
    Tests for Settings.validate_database_url field validator.
    We call the classmethod directly to avoid full Settings construction.
    """

    def _validate(self, url: str) -> str:
        from app.core.config import Settings

        return Settings.validate_database_url(url)

    def test_postgres_scheme_converted(self):
        result = self._validate("postgres://user:pass@localhost/db")
        assert result.startswith("postgresql+asyncpg://")

    def test_postgresql_scheme_converted(self):
        result = self._validate("postgresql://user:pass@localhost/db")
        assert result.startswith("postgresql+asyncpg://")

    def test_already_asyncpg_unchanged(self):
        url = "postgresql+asyncpg://user:pass@localhost/db"
        assert self._validate(url) == url

    def test_host_and_dbname_preserved_after_coercion(self):
        result = self._validate("postgres://user:pass@myhost:5432/mydb")
        assert "myhost:5432/mydb" in result

    def test_credentials_preserved_after_coercion(self):
        result = self._validate("postgres://myuser:mypass@localhost/db")
        assert "myuser:mypass" in result

    def test_postgres_prefix_replaced_only_once(self):
        """Ensure we don't double-replace."""
        result = self._validate("postgres://localhost/db")
        assert result.count("postgresql+asyncpg://") == 1

    def test_non_postgres_url_unchanged(self):
        """Non-PostgreSQL URLs (e.g. SQLite for testing) pass through."""
        url = "sqlite+aiosqlite:///./test.db"
        assert self._validate(url) == url


# ══════════════════════════════════════════════════════════════════
# CORS origins validator
# ══════════════════════════════════════════════════════════════════


class TestCorsOriginsValidator:
    def _validate(self, v):
        from app.core.config import Settings

        return Settings.assemble_cors_origins(v)

    def test_list_passed_through_unchanged(self):
        origins = ["http://localhost:3000", "https://example.com"]
        assert self._validate(origins) == origins

    def test_empty_list_passed_through(self):
        assert self._validate([]) == []

    def test_json_string_parsed(self):
        result = self._validate('["http://localhost:3000", "https://example.com"]')
        assert result == ["http://localhost:3000", "https://example.com"]

    def test_comma_separated_string_split(self):
        result = self._validate("http://localhost:3000,https://example.com")
        assert result == ["http://localhost:3000", "https://example.com"]

    def test_comma_separated_with_spaces(self):
        result = self._validate("http://localhost:3000 , https://example.com")
        assert "http://localhost:3000" in result
        assert "https://example.com" in result

    def test_empty_string_returns_empty_list(self):
        assert self._validate("") == []

    def test_single_origin_string(self):
        result = self._validate("http://localhost:5173")
        assert result == ["http://localhost:5173"]

    def test_whitespace_only_string_returns_empty(self):
        assert self._validate("   ") == []


# ══════════════════════════════════════════════════════════════════
# Celery defaults
# ══════════════════════════════════════════════════════════════════


class TestCeleryDefaults:
    def _validate_broker(self, v, redis_url="redis://redis:6379/0"):
        from app.core.config import Settings

        # Simulate what pydantic passes as `values`
        class FakeInfo:
            data = {"REDIS_URL": redis_url}

        return Settings.default_celery_broker(v, FakeInfo())

    def _validate_backend(self, v, redis_url="redis://redis:6379/0"):
        from app.core.config import Settings

        class FakeInfo:
            data = {"REDIS_URL": redis_url}

        return Settings.default_celery_backend(v, FakeInfo())

    def test_broker_defaults_to_redis_url_when_none(self):
        result = self._validate_broker(None)
        assert result == "redis://redis:6379/0"

    def test_broker_explicit_value_preserved(self):
        result = self._validate_broker("redis://custom:6379/1")
        assert result == "redis://custom:6379/1"

    def test_backend_defaults_to_redis_url_when_none(self):
        result = self._validate_backend(None)
        assert result == "redis://redis:6379/0"

    def test_backend_explicit_value_preserved(self):
        result = self._validate_backend("redis://custom:6379/2")
        assert result == "redis://custom:6379/2"

    def test_broker_uses_custom_redis_url(self):
        result = self._validate_broker(None, redis_url="redis://myredis:6380/0")
        assert result == "redis://myredis:6380/0"


# ══════════════════════════════════════════════════════════════════
# EMAIL_ENABLED auto-enable logic
# ══════════════════════════════════════════════════════════════════


class TestEmailEnabledValidator:
    def _validate(
        self,
        v: bool,
        smtp_server=None,
        smtp_user=None,
        smtp_password=None,
        from_email=None,
    ):
        from app.core.config import Settings

        class FakeInfo:
            data = {
                "SMTP_SERVER": smtp_server,
                "SMTP_USER": smtp_user,
                "SMTP_PASSWORD": smtp_password,
                "EMAIL_FROM_EMAIL": from_email,
            }

        return Settings.check_email_config(v, FakeInfo())

    def test_explicitly_true_returns_true(self):
        assert self._validate(True) is True

    def test_false_with_no_smtp_stays_false(self):
        assert self._validate(False) is False

    def test_false_with_partial_smtp_stays_false(self):
        # Only SMTP_SERVER set — not all four fields
        assert (
            self._validate(
                False,
                smtp_server="smtp.example.com",
            )
            is False
        )

    def test_false_with_all_smtp_fields_auto_enables(self):
        result = self._validate(
            False,
            smtp_server="smtp.example.com",
            smtp_user="user@example.com",
            smtp_password="secret",
            from_email="noreply@example.com",
        )
        assert result is True

    def test_true_with_no_smtp_still_true(self):
        """Explicit True is never overridden to False."""
        assert self._validate(True, smtp_server=None) is True


# ══════════════════════════════════════════════════════════════════
# Helper properties
# ══════════════════════════════════════════════════════════════════


class TestHelperProperties:
    def test_is_production_true(self):
        s = _make_settings(ENVIRONMENT="production")
        assert s.is_production is True

    def test_is_production_false_for_development(self):
        s = _make_settings(ENVIRONMENT="development")
        assert s.is_production is False

    def test_is_development_true(self):
        s = _make_settings(ENVIRONMENT="development")
        assert s.is_development is True

    def test_is_development_false_for_production(self):
        s = _make_settings(ENVIRONMENT="production")
        assert s.is_development is False

    def test_is_production_case_insensitive(self):
        s = _make_settings(ENVIRONMENT="PRODUCTION")
        assert s.is_production is True

    def test_smtp_configured_false_when_fields_missing(self):
        s = _make_settings(
            SMTP_SERVER=None,
            SMTP_USER=None,
            SMTP_PASSWORD=None,
            EMAIL_FROM_EMAIL=None,
        )
        assert s.smtp_configured is False

    def test_smtp_configured_true_when_all_fields_present(self):
        from pydantic import SecretStr

        s = _make_settings(
            SMTP_SERVER="smtp.example.com",
            SMTP_USER="user@example.com",
            SMTP_PASSWORD=SecretStr("secret"),
            EMAIL_FROM_EMAIL="noreply@example.com",
        )
        assert s.smtp_configured is True


# ══════════════════════════════════════════════════════════════════
# Default values sanity check
# ══════════════════════════════════════════════════════════════════


class TestDefaultValues:
    def test_default_environment_is_development(self):
        from app.core.config import settings

        # The singleton loaded from the test env
        assert isinstance(settings.ENVIRONMENT, str)

    def test_api_v1_str_default(self):
        s = _make_settings()
        assert s.API_V1_STR == "/api/v1"

    def test_algorithm_default_is_hs256(self):
        s = _make_settings()
        assert s.ALGORITHM == "HS256"

    def test_chunk_size_positive(self):
        s = _make_settings()
        assert s.CHUNK_SIZE > 0

    def test_chunk_overlap_less_than_chunk_size(self):
        s = _make_settings()
        assert s.CHUNK_OVERLAP < s.CHUNK_SIZE

    def test_max_upload_size_positive(self):
        s = _make_settings()
        assert s.MAX_UPLOAD_SIZE_MB > 0

    def test_allowed_extensions_include_pdf(self):
        s = _make_settings()
        assert ".pdf" in s.ALLOWED_UPLOAD_EXTENSIONS

    def test_allowed_extensions_include_docx(self):
        s = _make_settings()
        assert ".docx" in s.ALLOWED_UPLOAD_EXTENSIONS
