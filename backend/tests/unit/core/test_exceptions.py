"""
Unit tests for app/core/exceptions.py

Covers:
    - Correct HTTP status codes on every exception class
    - BaseAppException attributes (message, status_code, detail)
    - __repr__ output format
    - Inheritance chain (all subclass BaseAppException → Exception)
    - detail field accepts str, dict, None
    - Default messages when none provided

No DB, no network. Pure Python.
"""

import pytest

from app.core.exceptions import (
    BaseAppException,
    BadRequestException,
    UnauthorizedException,
    ForbiddenException,
    NotFoundException,
    ConflictException,
    ValidationException,
    InternalServerException,
    ServiceUnavailableException,
    SecurityPolicyException,
    AIServiceException,
    DocumentProcessingException,
    DebateException,
    IntegrationException,
    ExperimentException,
)


# ══════════════════════════════════════════════════════════════════
# Helper: map every exception class to its expected status code
# ══════════════════════════════════════════════════════════════════

EXCEPTION_STATUS_CODES = [
    (BadRequestException, 400),
    (UnauthorizedException, 401),
    (ForbiddenException, 403),
    (NotFoundException, 404),
    (ConflictException, 409),
    (ValidationException, 422),
    (InternalServerException, 500),
    (ServiceUnavailableException, 503),
    (SecurityPolicyException, 403),
    (AIServiceException, 503),
    (DocumentProcessingException, 400),
    (DebateException, 500),
    (IntegrationException, 503),
    (ExperimentException, 400),
]


# ══════════════════════════════════════════════════════════════════
# BaseAppException
# ══════════════════════════════════════════════════════════════════


class TestBaseAppException:
    def test_is_exception_subclass(self):
        assert issubclass(BaseAppException, Exception)

    def test_stores_message(self):
        exc = BaseAppException("something went wrong")
        assert exc.message == "something went wrong"

    def test_default_status_code_is_400(self):
        exc = BaseAppException("error")
        assert exc.status_code == 400

    def test_custom_status_code(self):
        exc = BaseAppException("error", status_code=503)
        assert exc.status_code == 503

    def test_detail_defaults_to_none(self):
        exc = BaseAppException("error")
        assert exc.detail is None

    def test_detail_accepts_string(self):
        exc = BaseAppException("error", detail="extra info")
        assert exc.detail == "extra info"

    def test_detail_accepts_dict(self):
        exc = BaseAppException("error", detail={"field": "email", "issue": "taken"})
        assert exc.detail["field"] == "email"

    def test_detail_accepts_list(self):
        exc = BaseAppException("error", detail=["item1", "item2"])
        assert exc.detail == ["item1", "item2"]

    def test_str_returns_message(self):
        exc = BaseAppException("my error message")
        assert str(exc) == "my error message"

    def test_repr_contains_class_name(self):
        exc = BaseAppException("my error")
        assert "BaseAppException" in repr(exc)

    def test_repr_contains_message(self):
        exc = BaseAppException("my error")
        assert "my error" in repr(exc)

    def test_repr_contains_status_code(self):
        exc = BaseAppException("my error", status_code=404)
        assert "404" in repr(exc)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(BaseAppException) as exc_info:
            raise BaseAppException("boom")
        assert exc_info.value.message == "boom"


# ══════════════════════════════════════════════════════════════════
# Status codes — parametrized across all subclasses
# ══════════════════════════════════════════════════════════════════


class TestStatusCodes:
    @pytest.mark.parametrize("exc_class,expected_code", EXCEPTION_STATUS_CODES)
    def test_default_status_code(self, exc_class, expected_code):
        exc = exc_class()
        assert exc.status_code == expected_code, (
            f"{exc_class.__name__} should have status {expected_code}, "
            f"got {exc.status_code}"
        )

    @pytest.mark.parametrize("exc_class,_", EXCEPTION_STATUS_CODES)
    def test_is_base_app_exception_subclass(self, exc_class, _):
        assert issubclass(exc_class, BaseAppException)

    @pytest.mark.parametrize("exc_class,_", EXCEPTION_STATUS_CODES)
    def test_is_exception_subclass(self, exc_class, _):
        assert issubclass(exc_class, Exception)

    @pytest.mark.parametrize("exc_class,_", EXCEPTION_STATUS_CODES)
    def test_can_be_raised_and_caught_as_base(self, exc_class, _):
        with pytest.raises(BaseAppException):
            raise exc_class("test error")

    @pytest.mark.parametrize("exc_class,_", EXCEPTION_STATUS_CODES)
    def test_can_be_raised_and_caught_as_itself(self, exc_class, _):
        with pytest.raises(exc_class):
            raise exc_class("test error")


# ══════════════════════════════════════════════════════════════════
# Default messages
# ══════════════════════════════════════════════════════════════════


class TestDefaultMessages:
    def test_bad_request_default_message(self):
        assert BadRequestException().message == "Bad request"

    def test_unauthorized_default_message(self):
        assert UnauthorizedException().message == "Authentication required"

    def test_forbidden_default_message(self):
        assert ForbiddenException().message == "Access forbidden"

    def test_not_found_default_message(self):
        assert NotFoundException().message == "Resource not found"

    def test_conflict_default_message(self):
        assert ConflictException().message == "Resource conflict"

    def test_validation_default_message(self):
        assert ValidationException().message == "Validation failed"

    def test_internal_server_default_message(self):
        assert InternalServerException().message == "Internal server error"

    def test_service_unavailable_default_message(self):
        assert "unavailable" in ServiceUnavailableException().message.lower()

    def test_security_policy_default_message(self):
        assert SecurityPolicyException().message == "Security policy violation"

    def test_ai_service_default_message(self):
        assert AIServiceException().message == "AI service error"

    def test_document_processing_default_message(self):
        assert (
            "document" in DocumentProcessingException().message.lower()
            or "processing" in DocumentProcessingException().message.lower()
        )

    def test_debate_default_message(self):
        assert DebateException().message == "Debate orchestration failed"

    def test_integration_default_message(self):
        assert IntegrationException().message == "Integration error"

    def test_experiment_default_message(self):
        assert ExperimentException().message == "Experiment error"


# ══════════════════════════════════════════════════════════════════
# Custom messages override defaults
# ══════════════════════════════════════════════════════════════════


class TestCustomMessages:
    @pytest.mark.parametrize("exc_class,_", EXCEPTION_STATUS_CODES)
    def test_custom_message_overrides_default(self, exc_class, _):
        exc = exc_class(message="custom message")
        assert exc.message == "custom message"

    @pytest.mark.parametrize("exc_class,_", EXCEPTION_STATUS_CODES)
    def test_custom_detail_stored(self, exc_class, _):
        exc = exc_class(detail={"key": "value"})
        assert exc.detail == {"key": "value"}


# ══════════════════════════════════════════════════════════════════
# repr
# ══════════════════════════════════════════════════════════════════


class TestRepr:
    @pytest.mark.parametrize("exc_class,expected_code", EXCEPTION_STATUS_CODES)
    def test_repr_contains_class_name(self, exc_class, expected_code):
        exc = exc_class("test")
        assert exc_class.__name__ in repr(exc)

    @pytest.mark.parametrize("exc_class,expected_code", EXCEPTION_STATUS_CODES)
    def test_repr_contains_status_code(self, exc_class, expected_code):
        exc = exc_class("test")
        assert str(expected_code) in repr(exc)
