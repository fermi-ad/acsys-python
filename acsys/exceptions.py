"""Custom exception hierarchy for the acsys library.

All exceptions raised by this library inherit from :class:`AcsysError`
so that callers can catch the entire family with a single ``except``
clause if desired.
"""


class AcsysError(Exception):
    """Base class for all acsys exceptions."""


class AcsysConfigurationError(AcsysError):
    """Raised for invalid or missing configuration (URL, credentials, etc.)."""


class AcsysAuthError(AcsysError):
    """Raised for authentication or authorization failures."""


class AcsysNetworkError(AcsysError):
    """Raised for network connectivity or transport-level errors."""


class AcsysAPIError(AcsysError):
    """Raised when the GraphQL API returns an application-level error.

    Attributes
    ----------
    errors : list
        The raw ``errors`` list from the GraphQL response, if available.
    """

    def __init__(self, message: str, errors: list | None = None):
        super().__init__(message)
        self.errors: list = errors or []


class AcsysStreamError(AcsysError):
    """Raised when a streaming subscription encounters an error."""


class AcsysTimeoutError(AcsysError, TimeoutError):
    """Raised when a request or stream operation times out."""
