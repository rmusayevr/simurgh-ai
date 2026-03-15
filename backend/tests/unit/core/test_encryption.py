"""
Unit tests for app/core/encryption.py

Covers:
    - encrypt/decrypt round-trip
    - Different plaintexts produce different ciphertexts
    - Empty string handling
    - Tampered ciphertext raises SecurityPolicyException
    - verify_encryption_key health check
    - Key rotation round-trip

Note: The global _cipher_suite is reset between tests via monkeypatch
so that each test gets a clean cipher state.
"""

import pytest

from app.core.exceptions import SecurityPolicyException


# ══════════════════════════════════════════════════════════════════
# Fixture: reset the global cipher between tests
# ══════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def reset_cipher(monkeypatch):
    """
    Reset the global _cipher_suite singleton before each test.

    This prevents state leakage between tests that might
    monkey-patch the ENCRYPTION_KEY.
    """
    import app.core.encryption as enc_module

    monkeypatch.setattr(enc_module, "_cipher_suite", None)
    yield
    monkeypatch.setattr(enc_module, "_cipher_suite", None)


# ══════════════════════════════════════════════════════════════════
# Import after fixture is ready
# ══════════════════════════════════════════════════════════════════


# Import lazily inside tests so the reset_cipher fixture takes effect.
def _get_funcs():
    from app.core.encryption import (
        encrypt_token,
        decrypt_token,
        verify_encryption_key,
        rotate_encryption,
        get_cipher,
    )

    return (
        encrypt_token,
        decrypt_token,
        verify_encryption_key,
        rotate_encryption,
        get_cipher,
    )


# ══════════════════════════════════════════════════════════════════
# encrypt_token
# ══════════════════════════════════════════════════════════════════


class TestEncryptToken:
    def test_returns_non_empty_string(self):
        encrypt_token, *_ = _get_funcs()
        result = encrypt_token("my-api-token")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_result_differs_from_plaintext(self):
        encrypt_token, *_ = _get_funcs()
        plain = "secret-api-key"
        assert encrypt_token(plain) != plain

    def test_two_encryptions_of_same_value_differ(self):
        """Fernet uses a random IV — same plaintext → different ciphertext each time."""
        encrypt_token, *_ = _get_funcs()
        plain = "same-secret"
        c1 = encrypt_token(plain)
        c2 = encrypt_token(plain)
        assert c1 != c2

    def test_empty_string_returns_empty_string(self):
        encrypt_token, *_ = _get_funcs()
        assert encrypt_token("") == ""

    def test_long_string_accepted(self):
        encrypt_token, *_ = _get_funcs()
        long_secret = "x" * 10_000
        result = encrypt_token(long_secret)
        assert len(result) > 0

    def test_special_characters_accepted(self):
        encrypt_token, *_ = _get_funcs()
        result = encrypt_token("token!@#$%^&*()_+-=[]{}|;':\",./<>?")
        assert len(result) > 0

    def test_unicode_accepted(self):
        encrypt_token, *_ = _get_funcs()
        result = encrypt_token("tëst-tökén-üñíçödé")
        assert len(result) > 0


# ══════════════════════════════════════════════════════════════════
# decrypt_token
# ══════════════════════════════════════════════════════════════════


class TestDecryptToken:
    def test_round_trip_restores_original(self):
        encrypt_token, decrypt_token, *_ = _get_funcs()
        plain = "my-secret-jira-token"
        assert decrypt_token(encrypt_token(plain)) == plain

    def test_round_trip_empty_string(self):
        encrypt_token, decrypt_token, *_ = _get_funcs()
        assert decrypt_token("") == ""

    def test_round_trip_special_characters(self):
        encrypt_token, decrypt_token, *_ = _get_funcs()
        plain = "tok!@#$%^&*()"
        assert decrypt_token(encrypt_token(plain)) == plain

    def test_round_trip_unicode(self):
        encrypt_token, decrypt_token, *_ = _get_funcs()
        plain = "tëst-tökén"
        assert decrypt_token(encrypt_token(plain)) == plain

    def test_round_trip_long_value(self):
        encrypt_token, decrypt_token, *_ = _get_funcs()
        plain = "A" * 5_000
        assert decrypt_token(encrypt_token(plain)) == plain

    def test_tampered_ciphertext_raises(self):
        encrypt_token, decrypt_token, *_ = _get_funcs()
        ciphertext = encrypt_token("sensitive-data")
        # Flip characters near the end to tamper the MAC
        tampered = ciphertext[:-4] + "XXXX"
        with pytest.raises(SecurityPolicyException):
            decrypt_token(tampered)

    def test_random_string_raises(self):
        _, decrypt_token, *_ = _get_funcs()
        with pytest.raises(SecurityPolicyException):
            decrypt_token("this-is-not-a-fernet-token")

    def test_plaintext_string_raises(self):
        _, decrypt_token, *_ = _get_funcs()
        with pytest.raises(SecurityPolicyException):
            decrypt_token("plain-text-not-encrypted")

    def test_multiple_round_trips_consistent(self):
        """Decrypt can be called multiple times on the same ciphertext."""
        encrypt_token, decrypt_token, *_ = _get_funcs()
        plain = "repeat-me"
        ciphertext = encrypt_token(plain)
        assert decrypt_token(ciphertext) == plain
        assert decrypt_token(ciphertext) == plain


# ══════════════════════════════════════════════════════════════════
# verify_encryption_key
# ══════════════════════════════════════════════════════════════════


class TestVerifyEncryptionKey:
    def test_returns_true_with_valid_key(self):
        _, _, verify_encryption_key, *_ = _get_funcs()
        assert verify_encryption_key() is True

    def test_returns_true_with_custom_test_string(self):
        _, _, verify_encryption_key, *_ = _get_funcs()
        assert verify_encryption_key(test_string="custom-test-value") is True

    def test_returns_false_when_cipher_raises(self, monkeypatch):
        _, _, verify_encryption_key, *_ = _get_funcs()
        import app.core.encryption as enc_module

        def bad_encrypt(_):
            raise RuntimeError("simulated failure")

        monkeypatch.setattr(enc_module, "encrypt_token", bad_encrypt)
        assert verify_encryption_key() is False


# ══════════════════════════════════════════════════════════════════
# rotate_encryption
# ══════════════════════════════════════════════════════════════════


class TestRotateEncryption:
    def test_rotated_value_decryptable_with_new_key(self):
        from cryptography.fernet import Fernet

        _, _, _, rotate_encryption, _ = _get_funcs()

        old_key = Fernet.generate_key().decode()
        new_key = Fernet.generate_key().decode()

        # Encrypt with old key manually
        old_cipher = Fernet(old_key.encode())
        old_encrypted = old_cipher.encrypt(b"rotate-me").decode()

        # Rotate to new key
        new_encrypted = rotate_encryption(old_encrypted, old_key, new_key)

        # Decrypt with new key
        new_cipher = Fernet(new_key.encode())
        decrypted = new_cipher.decrypt(new_encrypted.encode()).decode()
        assert decrypted == "rotate-me"

    def test_rotated_value_differs_from_original(self):
        from cryptography.fernet import Fernet

        _, _, _, rotate_encryption, _ = _get_funcs()

        old_key = Fernet.generate_key().decode()
        new_key = Fernet.generate_key().decode()

        old_cipher = Fernet(old_key.encode())
        old_encrypted = old_cipher.encrypt(b"data").decode()

        new_encrypted = rotate_encryption(old_encrypted, old_key, new_key)
        assert new_encrypted != old_encrypted

    def test_wrong_old_key_raises(self):
        from cryptography.fernet import Fernet

        _, _, _, rotate_encryption, _ = _get_funcs()

        real_key = Fernet.generate_key().decode()
        wrong_key = Fernet.generate_key().decode()
        new_key = Fernet.generate_key().decode()

        cipher = Fernet(real_key.encode())
        encrypted = cipher.encrypt(b"secret").decode()

        with pytest.raises(SecurityPolicyException):
            rotate_encryption(encrypted, wrong_key, new_key)


# ══════════════════════════════════════════════════════════════════
# get_cipher singleton behaviour
# ══════════════════════════════════════════════════════════════════


class TestGetCipher:
    def test_returns_fernet_instance(self):
        from cryptography.fernet import Fernet

        _, _, _, _, get_cipher = _get_funcs()
        cipher = get_cipher()
        assert isinstance(cipher, Fernet)

    def test_second_call_returns_same_instance(self):
        _, _, _, _, get_cipher = _get_funcs()
        c1 = get_cipher()
        c2 = get_cipher()
        assert c1 is c2  # singleton — same object

    def test_invalid_key_raises_value_error(self, monkeypatch):
        import app.core.encryption as enc_module
        from unittest.mock import MagicMock

        # Reset cipher so it tries to re-initialise
        monkeypatch.setattr(enc_module, "_cipher_suite", None)

        # Patch ENCRYPTION_KEY to return an invalid value
        bad_settings = MagicMock()
        bad_settings.ENCRYPTION_KEY.get_secret_value.return_value = (
            "not-a-valid-fernet-key"
        )
        monkeypatch.setattr(enc_module, "settings", bad_settings)

        with pytest.raises(ValueError):
            enc_module.get_cipher()
