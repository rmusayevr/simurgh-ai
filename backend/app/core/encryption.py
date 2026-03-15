"""
Encryption utilities for sensitive data.

Uses Fernet (symmetric encryption) for:
    - API tokens (Jira, Confluence, etc.)
    - User secrets
    - Sensitive configuration values

Security notes:
    - ENCRYPTION_KEY must be 32 bytes, base64-encoded
    - Keys are cached in memory for performance
    - Decryption failures raise SecurityPolicyException
"""

import structlog
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.exceptions import SecurityPolicyException

logger = structlog.get_logger(__name__)

# Global cipher instance (singleton pattern for performance)
_cipher_suite: Optional[Fernet] = None


def get_cipher() -> Fernet:
    """
    Get or initialize the Fernet cipher suite.

    Lazily initializes cipher on first use and caches for subsequent calls.

    Returns:
        Fernet: Initialized cipher suite

    Raises:
        ValueError: If ENCRYPTION_KEY is missing or invalid format
    """
    global _cipher_suite

    if _cipher_suite is None:
        key = settings.ENCRYPTION_KEY.get_secret_value()

        if not key:
            logger.critical("encryption_key_missing", environment=settings.ENVIRONMENT)
            raise ValueError(
                "ENCRYPTION_KEY not configured. Set in environment variables."
            )

        try:
            _cipher_suite = Fernet(key.encode() if isinstance(key, str) else key)
            logger.info("encryption_cipher_initialized")
        except Exception as e:
            logger.critical("encryption_key_invalid", error=str(e))
            raise ValueError(
                "Invalid ENCRYPTION_KEY format. Must be 32 bytes, base64-encoded. "
                "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            ) from e

    return _cipher_suite


def encrypt_token(plain_text: str) -> str:
    """
    Encrypt a plaintext string.

    Args:
        plain_text: String to encrypt (e.g., API token, password)

    Returns:
        str: Base64-encoded encrypted string

    Examples:
        >>> encrypted = encrypt_token("my-secret-api-key")
        >>> print(encrypted)
        'gAAAAABh...'
    """
    if not plain_text:
        return ""

    try:
        cipher = get_cipher()
        encrypted_bytes = cipher.encrypt(plain_text.encode())
        return encrypted_bytes.decode()
    except Exception as e:
        logger.error("encryption_failed", error=str(e))
        raise SecurityPolicyException("Failed to encrypt data") from e


def decrypt_token(encrypted_text: str) -> str:
    """
    Decrypt an encrypted string.

    Args:
        encrypted_text: Base64-encoded encrypted string

    Returns:
        str: Decrypted plaintext string

    Raises:
        SecurityPolicyException: If decryption fails (invalid token or tampered data)

    Examples:
        >>> decrypted = decrypt_token("gAAAAABh...")
        >>> print(decrypted)
        'my-secret-api-key'
    """
    if not encrypted_text:
        return ""

    try:
        cipher = get_cipher()
        decrypted_bytes = cipher.decrypt(encrypted_text.encode())
        return decrypted_bytes.decode()
    except InvalidToken:
        logger.warning(
            "decryption_failed_invalid_token",
            hint="Token may be corrupted or encrypted with different key",
        )
        raise SecurityPolicyException(
            "Failed to decrypt data. Token is invalid or corrupted."
        )
    except Exception as e:
        logger.error(
            "decryption_failed_unexpected", error=str(e), error_type=type(e).__name__
        )
        raise SecurityPolicyException(f"Unexpected decryption error: {str(e)}") from e


def rotate_encryption(old_encrypted: str, old_key: str, new_key: str) -> str:
    """
    Re-encrypt data with a new encryption key.

    Useful for key rotation without decrypting to plaintext in application memory.

    Args:
        old_encrypted: Data encrypted with old key
        old_key: Previous encryption key (base64-encoded)
        new_key: New encryption key (base64-encoded)

    Returns:
        str: Data re-encrypted with new key

    Example:
        >>> new_encrypted = rotate_encryption(
        ...     old_encrypted="gAAAAABh...",
        ...     old_key=old_settings.ENCRYPTION_KEY,
        ...     new_key=new_settings.ENCRYPTION_KEY
        ... )
    """
    try:
        # Decrypt with old key
        old_cipher = Fernet(old_key.encode() if isinstance(old_key, str) else old_key)
        plaintext = old_cipher.decrypt(old_encrypted.encode()).decode()

        # Encrypt with new key
        new_cipher = Fernet(new_key.encode() if isinstance(new_key, str) else new_key)
        new_encrypted = new_cipher.encrypt(plaintext.encode()).decode()

        logger.info("encryption_key_rotated")
        return new_encrypted
    except Exception as e:
        logger.error("key_rotation_failed", error=str(e))
        raise SecurityPolicyException("Failed to rotate encryption key") from e


def verify_encryption_key(test_string: str = "test") -> bool:
    """
    Verify that encryption/decryption works correctly.

    Useful for health checks and startup validation.

    Args:
        test_string: String to use for round-trip test

    Returns:
        bool: True if encryption is working correctly

    Example:
        >>> if verify_encryption_key():
        ...     print("Encryption configured correctly")
    """
    try:
        encrypted = encrypt_token(test_string)
        decrypted = decrypt_token(encrypted)
        return decrypted == test_string
    except Exception as e:
        logger.error("encryption_verification_failed", error=str(e))
        return False
