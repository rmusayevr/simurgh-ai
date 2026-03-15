"""
Unit tests for app/core/security.py

Covers:
    - Password hashing and verification (bcrypt)
    - Access token creation and decoding
    - Refresh token creation and decoding
    - Token type validation
    - Token expiration and utility helpers
    - Edge cases: empty inputs, tampered tokens, wrong types

No DB, no network. All tests run in < 1s.
"""

import pytest
from datetime import timedelta, datetime, timezone

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_token_subject,
    verify_token_type,
    get_token_expiration,
    is_token_expired,
    get_time_until_expiration,
)
from app.core.exceptions import UnauthorizedException, SecurityPolicyException


# ══════════════════════════════════════════════════════════════════
# Password hashing
# ══════════════════════════════════════════════════════════════════


class TestHashPassword:
    def test_returns_bcrypt_hash(self):
        result = hash_password("Password123!")
        assert result.startswith("$2b$")

    def test_hash_is_different_from_plaintext(self):
        plain = "Password123!"
        assert hash_password(plain) != plain

    def test_same_password_produces_different_hashes(self):
        """bcrypt uses a random salt — two hashes of the same password differ."""
        h1 = hash_password("Password123!")
        h2 = hash_password("Password123!")
        assert h1 != h2

    def test_minimum_length_accepted(self):
        result = hash_password("12345678")  # exactly 8 chars
        assert result.startswith("$2b$")

    def test_raises_on_empty_password(self):
        with pytest.raises(SecurityPolicyException):
            hash_password("")

    def test_raises_on_too_short_password(self):
        with pytest.raises(SecurityPolicyException):
            hash_password("short")  # 5 chars < 8

    def test_long_password_accepted(self):
        # bcrypt silently truncates at 72 bytes; passwords longer than that
        # cause an error in this implementation. 72 chars is the safe maximum.
        result = hash_password("A" * 72)
        assert result.startswith("$2b$")

    def test_special_characters_accepted(self):
        result = hash_password("P@$$w0rd!#%^&*()")
        assert result.startswith("$2b$")

    def test_unicode_password_accepted(self):
        result = hash_password("Pässwört123!")
        assert result.startswith("$2b$")


# ══════════════════════════════════════════════════════════════════
# Password verification
# ══════════════════════════════════════════════════════════════════


class TestVerifyPassword:
    def test_correct_password_returns_true(self):
        plain = "Password123!"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_wrong_password_returns_false(self):
        hashed = hash_password("Password123!")
        assert verify_password("WrongPassword!", hashed) is False

    def test_empty_plain_returns_false(self):
        hashed = hash_password("Password123!")
        assert verify_password("", hashed) is False

    def test_empty_hash_returns_false(self):
        assert verify_password("Password123!", "") is False

    def test_both_empty_returns_false(self):
        assert verify_password("", "") is False

    def test_case_sensitive(self):
        hashed = hash_password("Password123!")
        assert verify_password("password123!", hashed) is False

    def test_extra_whitespace_returns_false(self):
        hashed = hash_password("Password123!")
        assert verify_password(" Password123!", hashed) is False

    def test_round_trip_unicode(self):
        plain = "Pässwört123!"
        assert verify_password(plain, hash_password(plain)) is True


# ══════════════════════════════════════════════════════════════════
# Access token creation
# ══════════════════════════════════════════════════════════════════


class TestCreateAccessToken:
    def test_returns_non_empty_string(self):
        token = create_access_token(subject="42")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_has_three_jwt_parts(self):
        token = create_access_token(subject="42")
        parts = token.split(".")
        assert len(parts) == 3

    def test_subject_encoded_correctly(self):
        token = create_access_token(subject="99")
        payload = decode_token(token)
        assert payload["sub"] == "99"

    def test_type_is_access(self):
        token = create_access_token(subject="1")
        payload = decode_token(token)
        assert payload["type"] == "access"

    def test_contains_expiry(self):
        token = create_access_token(subject="1")
        payload = decode_token(token)
        assert "exp" in payload

    def test_contains_issued_at(self):
        token = create_access_token(subject="1")
        payload = decode_token(token)
        assert "iat" in payload

    def test_custom_expiry_respected(self):
        short = create_access_token(subject="1", expires_delta=timedelta(minutes=1))
        long = create_access_token(subject="1", expires_delta=timedelta(days=30))
        short_exp = decode_token(short)["exp"]
        long_exp = decode_token(long)["exp"]
        assert long_exp > short_exp

    def test_additional_claims_included(self):
        token = create_access_token(
            subject="1",
            additional_claims={"role": "ADMIN", "org": "test-org"},
        )
        payload = decode_token(token)
        assert payload["role"] == "ADMIN"
        assert payload["org"] == "test-org"

    def test_integer_subject_coerced_to_string(self):
        token = create_access_token(subject=42)
        payload = decode_token(token)
        assert payload["sub"] == "42"


# ══════════════════════════════════════════════════════════════════
# Refresh token creation
# ══════════════════════════════════════════════════════════════════


class TestCreateRefreshToken:
    def test_returns_non_empty_string(self):
        token = create_refresh_token(subject="1")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_type_is_refresh(self):
        token = create_refresh_token(subject="1")
        payload = decode_token(token)
        assert payload["type"] == "refresh"

    def test_refresh_expires_later_than_access(self):
        access = create_access_token(subject="1")
        refresh = create_refresh_token(subject="1")
        access_exp = decode_token(access)["exp"]
        refresh_exp = decode_token(refresh)["exp"]
        assert refresh_exp > access_exp

    def test_subject_preserved(self):
        token = create_refresh_token(subject="777")
        payload = decode_token(token)
        assert payload["sub"] == "777"

    def test_additional_claims_supported(self):
        token = create_refresh_token(
            subject="1",
            additional_claims={"device": "mobile"},
        )
        payload = decode_token(token)
        assert payload["device"] == "mobile"


# ══════════════════════════════════════════════════════════════════
# Token decoding
# ══════════════════════════════════════════════════════════════════


class TestDecodeToken:
    def test_valid_token_returns_payload(self):
        token = create_access_token(subject="5")
        payload = decode_token(token)
        assert payload["sub"] == "5"

    def test_expired_token_raises_unauthorized(self):
        token = create_access_token(
            subject="1",
            expires_delta=timedelta(seconds=-1),  # already expired
        )
        with pytest.raises(UnauthorizedException, match="expired"):
            decode_token(token)

    def test_tampered_signature_raises_unauthorized(self):
        token = create_access_token(subject="1")
        # Flip the last character to tamper the signature
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        with pytest.raises(UnauthorizedException):
            decode_token(tampered)

    def test_random_string_raises_unauthorized(self):
        with pytest.raises(UnauthorizedException):
            decode_token("not.a.jwt")

    def test_empty_string_raises_unauthorized(self):
        with pytest.raises(UnauthorizedException):
            decode_token("")

    def test_type_validation_passes_for_correct_type(self):
        token = create_access_token(subject="1")
        payload = decode_token(token, expected_type="access")
        assert payload["sub"] == "1"

    def test_type_mismatch_raises_unauthorized(self):
        """Passing a refresh token where an access token is expected."""
        refresh = create_refresh_token(subject="1")
        with pytest.raises(UnauthorizedException):
            decode_token(refresh, expected_type="access")

    def test_type_mismatch_access_as_refresh_raises(self):
        access = create_access_token(subject="1")
        with pytest.raises(UnauthorizedException):
            decode_token(access, expected_type="refresh")

    def test_no_expected_type_skips_type_check(self):
        """expected_type=None should not validate the type field."""
        refresh = create_refresh_token(subject="1")
        payload = decode_token(refresh, expected_type=None)
        assert payload["type"] == "refresh"


# ══════════════════════════════════════════════════════════════════
# get_token_subject
# ══════════════════════════════════════════════════════════════════


class TestGetTokenSubject:
    def test_returns_subject_string(self):
        token = create_access_token(subject="123")
        assert get_token_subject(token) == "123"

    def test_with_expected_type(self):
        token = create_access_token(subject="55")
        assert get_token_subject(token, expected_type="access") == "55"

    def test_wrong_type_raises(self):
        access = create_access_token(subject="1")
        with pytest.raises(UnauthorizedException):
            get_token_subject(access, expected_type="refresh")


# ══════════════════════════════════════════════════════════════════
# verify_token_type
# ══════════════════════════════════════════════════════════════════


class TestVerifyTokenType:
    def test_access_token_matches_access(self):
        token = create_access_token(subject="1")
        assert verify_token_type(token, "access") is True

    def test_access_token_does_not_match_refresh(self):
        token = create_access_token(subject="1")
        assert verify_token_type(token, "refresh") is False

    def test_refresh_token_matches_refresh(self):
        token = create_refresh_token(subject="1")
        assert verify_token_type(token, "refresh") is True

    def test_refresh_token_does_not_match_access(self):
        token = create_refresh_token(subject="1")
        assert verify_token_type(token, "access") is False

    def test_invalid_token_returns_false(self):
        assert verify_token_type("garbage.token.value", "access") is False


# ══════════════════════════════════════════════════════════════════
# Token utility helpers
# ══════════════════════════════════════════════════════════════════


class TestTokenUtilities:
    def test_get_token_expiration_returns_datetime(self):
        token = create_access_token(subject="1")
        exp = get_token_expiration(token)
        assert isinstance(exp, datetime)
        assert exp.tzinfo is not None  # timezone-aware

    def test_get_token_expiration_is_in_future(self):
        token = create_access_token(subject="1")
        exp = get_token_expiration(token)
        assert exp > datetime.now(timezone.utc)

    def test_is_token_expired_false_for_fresh_token(self):
        token = create_access_token(subject="1")
        assert is_token_expired(token) is False

    def test_is_token_expired_true_for_expired_token(self):
        token = create_access_token(
            subject="1",
            expires_delta=timedelta(seconds=-1),
        )
        assert is_token_expired(token) is True

    def test_is_token_expired_true_for_garbage(self):
        assert is_token_expired("not.a.real.token") is True

    def test_get_time_until_expiration_positive_for_fresh(self):
        token = create_access_token(subject="1")
        remaining = get_time_until_expiration(token)
        assert remaining.total_seconds() > 0

    def test_get_time_until_expiration_raises_for_expired(self):
        # get_token_expiration calls decode_token which raises UnauthorizedException
        # on expired tokens — there is no way to get a negative timedelta from it
        token = create_access_token(
            subject="1",
            expires_delta=timedelta(seconds=-60),
        )
        with pytest.raises(UnauthorizedException):
            get_time_until_expiration(token)
