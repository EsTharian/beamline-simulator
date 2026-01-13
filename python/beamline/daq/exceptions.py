"""Custom exceptions for beamline DAQ layer."""


class BeamlineError(Exception):
    """Base exception for all beamline DAQ errors."""

    pass


class ConnectionError(BeamlineError):
    """Raised when connection to device server fails or is lost."""

    pass


class ProtocolError(BeamlineError):
    """Raised when protocol communication fails or server returns error.

    Attributes:
        error_code: Server error code (e.g., "UNKNOWN_PV", "INVALID_VALUE")
        message: Human-readable error message
    """

    def __init__(self, error_code: str, message: str | None = None) -> None:
        """Initialize protocol error.

        Args:
            error_code: Server error code
            message: Optional error message
        """
        self.error_code = error_code
        self.message = message
        super().__init__(message or f"Protocol error: {error_code}")


class TimeoutError(BeamlineError):
    """Raised when operation times out."""

    pass
