from __future__ import annotations

from typing import Any


class SDKError(Exception):
    """Base SDK exception."""


class ConfigError(SDKError):
    """Invalid SDK configuration."""


class ClientClosedError(SDKError):
    """Client was used after being closed."""


class AuthError(SDKError):
    """Authentication or token acquisition failure."""


class ValidationError(SDKError):
    """Request or response validation failure."""


class SerializationError(SDKError):
    """Serialization or deserialization failure."""


class UnexpectedResponseError(ValidationError):
    """Unexpected API response shape or content."""


class TransportError(SDKError):
    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.details = details


class RequestTimeoutError(TransportError):
    """Request timed out."""


class APIError(SDKError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
        response_text: str | None = None,
        response_json: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.response_text = response_text
        self.response_json = response_json


class RetryableAPIError(APIError):
    """Transient API error."""


class NonRetryableAPIError(APIError):
    """Permanent API error."""


class BatchRequestError(SDKError):
    def __init__(self, message: str, *, failures: dict[str, Exception]) -> None:
        super().__init__(message)
        self.failures = failures


class RunnerError(SDKError):
    """Base runner error."""


class PricingComputationError(RunnerError):
    """Pricing execution failed."""


class ResultParsingError(RunnerError):
    """Failed to parse pricing or API result."""


class SetCreationError(RunnerError):
    """Failed to create one or more remote sets."""


class QmlInputNotFoundError(RunnerError):
    """Required QML input file not found."""


class QmlVerificationError(RunnerError):
    """QML verification failed."""


class DumpError(RunnerError):
    """Dumping output failed."""


class XmlUpdateError(RunnerError):
    """XML updater failed."""


class OverrideError(RunnerError):
    """Base override error."""


class OverrideValidationError(OverrideError):
    """Override spec is invalid."""


class OverrideApplicationError(OverrideError):
    """Failed to apply one or more overrides."""
