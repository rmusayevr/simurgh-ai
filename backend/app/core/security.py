"""
Security utilities for authentication and authorization.

Provides:
    - Password hashing and verification (bcrypt)
    - JWT token generation and validation
    - Access token management
    - Refresh token management

Security best practices:
    - Bcrypt for password hashing (adaptive cost)
    - Short-lived access tokens (default: 7 days)
    - Long-lived refresh tokens (default: 30 days)
    - Token type validation ("access" vs "refresh")
"""

import structlog
from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional, Dict

import bcrypt
from jose import jwt, JWTError

from app.core.config import settings
from app.core.exceptions import UnauthorizedException, SecurityPolicyException

logger = structlog.get_logger(__name__)


# ==================== Password Hashing ====================


def hash_password(password: str) -> str:
    """
    Generate a secure bcrypt hash for a password.

    Args:
        password: Plain text password to hash

    Returns:
        str: Bcrypt hash (UTF-8 decoded)

    Raises:
        SecurityPolicyException: If password is empty

    Example:
        >>> hashed = hash_password("my-secure-password")
        >>> print(hashed)
        '$2b$12$...'
    """
    if not password:
        raise SecurityPolicyException("Password cannot be empty")

    if len(password) < 8:
        raise SecurityPolicyException("Password must be at least 8 characters")

    try:
        pwd_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt(rounds=12)  # 12 rounds is secure and performant
        hashed = bcrypt.hashpw(pwd_bytes, salt)
        return hashed.decode("utf-8")
    except Exception as e:
        logger.error("password_hashing_failed", error=str(e))
        raise SecurityPolicyException("Failed to hash password") from e


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a bcrypt hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Bcrypt hash to compare against

    Returns:
        bool: True if password matches hash

    Example:
        >>> is_valid = verify_password("my-password", stored_hash)
        >>> if is_valid:
        ...     print("Password correct!")
    """
    if not plain_password or not hashed_password:
        return False

    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except Exception as e:
        logger.warning("password_verification_error", error=str(e))
        return False


# ==================== JWT Token Management ====================


def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a short-lived access token for API authentication.

    Args:
        subject: Token subject (typically user ID)
        expires_delta: Custom expiration time (default: from settings)
        additional_claims: Additional JWT claims to include

    Returns:
        str: Encoded JWT token

    Example:
        >>> token = create_access_token(subject="user_123")
        >>> # Use in Authorization: Bearer {token}
    """
    delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _encode_token(
        subject=subject,
        expires_delta=delta,
        token_type="access",
        additional_claims=additional_claims,
    )


def create_refresh_token(
    subject: Union[str, Any],
    additional_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a long-lived refresh token.

    Refresh tokens are used to obtain new access tokens without re-authentication.

    Args:
        subject: Token subject (typically user ID)
        additional_claims: Additional JWT claims to include

    Returns:
        str: Encoded JWT token

    Example:
        >>> refresh_token = create_refresh_token(subject="user_123")
        >>> # Store securely (e.g., httpOnly cookie)
    """
    delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _encode_token(
        subject=subject,
        expires_delta=delta,
        token_type="refresh",
        additional_claims=additional_claims,
    )


def decode_token(token: str, expected_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string to decode
        expected_type: Expected token type ("access" or "refresh"), or None to skip validation

    Returns:
        dict: Decoded token payload

    Raises:
        UnauthorizedException: If token is invalid, expired, or wrong type

    Example:
        >>> payload = decode_token(token, expected_type="access")
        >>> user_id = payload["sub"]
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.ALGORITHM],
        )

        # Validate token type if specified
        if expected_type and payload.get("type") != expected_type:
            logger.warning(
                "token_type_mismatch",
                expected=expected_type,
                actual=payload.get("type"),
            )
            raise UnauthorizedException(
                message=f"Invalid token type. Expected {expected_type}.",
                detail={"expected": expected_type, "actual": payload.get("type")},
            )

        return payload

    except jwt.ExpiredSignatureError:
        logger.info("token_expired")
        raise UnauthorizedException("Token has expired")
    except JWTError as e:
        logger.warning("token_decode_failed", error=str(e))
        raise UnauthorizedException("Invalid token")


def get_token_subject(token: str, expected_type: Optional[str] = None) -> str:
    """
    Extract the subject (user ID) from a JWT token.

    Args:
        token: JWT token string
        expected_type: Expected token type ("access" or "refresh")

    Returns:
        str: Token subject (user ID)

    Raises:
        UnauthorizedException: If token is invalid

    Example:
        >>> user_id = get_token_subject(token, expected_type="access")
    """
    payload = decode_token(token, expected_type)
    subject = payload.get("sub")

    if not subject:
        raise UnauthorizedException("Token missing subject")

    return subject


def verify_token_type(token: str, expected_type: str) -> bool:
    """
    Check if token is of expected type without raising exception.

    Args:
        token: JWT token string
        expected_type: Expected token type

    Returns:
        bool: True if token type matches
    """
    try:
        payload = decode_token(token, expected_type=None)
        return payload.get("type") == expected_type
    except UnauthorizedException:
        return False


# ==================== Private Helpers ====================


def _encode_token(
    subject: Union[str, Any],
    expires_delta: timedelta,
    token_type: str,
    additional_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Private helper to standardize JWT encoding.

    Args:
        subject: Token subject
        expires_delta: Time until expiration
        token_type: Type of token ("access" or "refresh")
        additional_claims: Additional claims to include

    Returns:
        str: Encoded JWT token
    """
    expire = datetime.now(timezone.utc) + expires_delta

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": token_type,
        "iat": datetime.now(timezone.utc),  # Issued at
    }

    # Merge additional claims
    if additional_claims:
        to_encode.update(additional_claims)

    try:
        encoded = jwt.encode(
            to_encode,
            settings.SECRET_KEY.get_secret_value(),
            algorithm=settings.ALGORITHM,
        )

        logger.debug(
            "token_created",
            type=token_type,
            subject=str(subject),
            expires_in=expires_delta.total_seconds(),
        )

        return encoded

    except JWTError as e:
        logger.error("jwt_encoding_failed", error=str(e), type=token_type)
        raise SecurityPolicyException("Failed to generate secure token") from e


# ==================== Token Utilities ====================


def get_token_expiration(token: str) -> datetime:
    """
    Get expiration datetime from token.

    Args:
        token: JWT token string

    Returns:
        datetime: Token expiration time (UTC)
    """
    payload = decode_token(token, expected_type=None)
    exp_timestamp = payload.get("exp")

    if not exp_timestamp:
        raise UnauthorizedException("Token missing expiration")

    return datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)


def is_token_expired(token: str) -> bool:
    """
    Check if token is expired without raising exception.

    Args:
        token: JWT token string

    Returns:
        bool: True if token is expired
    """
    try:
        expiration = get_token_expiration(token)
        return datetime.now(timezone.utc) >= expiration
    except UnauthorizedException:
        return True


def get_time_until_expiration(token: str) -> timedelta:
    """
    Get remaining time until token expires.

    Args:
        token: JWT token string

    Returns:
        timedelta: Time remaining (negative if expired)
    """
    expiration = get_token_expiration(token)
    return expiration - datetime.now(timezone.utc)
