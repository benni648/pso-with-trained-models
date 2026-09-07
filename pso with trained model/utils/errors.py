"""
Custom exception classes and error handling for the PSO Traffic API.

All API exceptions inherit from TrafficAPIError.
The handle_error() function maps exceptions to standardized HTTP responses.
"""

from datetime import datetime
from typing import Dict, Any, Tuple, Optional


# ── BASE EXCEPTION ──────────────────────────────────────────────

class TrafficAPIError(Exception):
    """Base exception for all API errors."""

    def __init__(
        self,
        message: str = "An error occurred",
        status_code: int = 400,
        error_code: str = "TRAFFIC_API_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


# ── SPECIFIC EXCEPTIONS ─────────────────────────────────────────

class ModelNotFoundError(TrafficAPIError):
    """Raised when the ML model file is not found."""

    def __init__(self, model_path: str = ""):
        super().__init__(
            message=f"Model not found: {model_path}",
            status_code=404,
            error_code="MODEL_NOT_FOUND",
            details={"model_path": model_path},
        )


class DatasetNotFoundError(TrafficAPIError):
    """Raised when a dataset is not found."""

    def __init__(self, dataset_id: int = 0):
        super().__init__(
            message=f"Dataset not found: {dataset_id}",
            status_code=404,
            error_code="DATASET_NOT_FOUND",
            details={"dataset_id": dataset_id},
        )


class InvalidJSONError(TrafficAPIError):
    """Raised when request body is not valid JSON."""

    def __init__(self, details: Optional[Dict] = None):
        super().__init__(
            message="Request body must be valid JSON",
            status_code=400,
            error_code="INVALID_JSON",
            details=details,
        )


class MissingFieldError(TrafficAPIError):
    """Raised when a required field is missing from the request."""

    def __init__(self, fields: list = None):
        fields = fields or []
        super().__init__(
            message=f"Missing required fields: {', '.join(fields)}",
            status_code=422,
            error_code="MISSING_FIELD",
            details={"missing_fields": fields},
        )


class InvalidCongestionLevelError(TrafficAPIError):
    """Raised when congestion_level is not LOW, MEDIUM, or HIGH."""

    def __init__(self, provided: str = ""):
        super().__init__(
            message=f"Invalid congestion level: '{provided}'. Must be LOW, MEDIUM, or HIGH.",
            status_code=422,
            error_code="INVALID_CONGESTION_LEVEL",
            details={"provided": provided, "valid_options": ["LOW", "MEDIUM", "HIGH"]},
        )


class PredictionError(TrafficAPIError):
    """Raised when prediction fails."""

    def __init__(self, message: str = "Prediction failed", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="PREDICTION_ERROR",
            details=details,
        )


class OptimizationError(TrafficAPIError):
    """Raised when optimization fails."""

    def __init__(self, message: str = "Optimization failed", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="OPTIMIZATION_ERROR",
            details=details,
        )


class AuthenticationError(TrafficAPIError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTHENTICATION_ERROR",
        )


class AuthorizationError(TrafficAPIError):
    """Raised when user lacks permission."""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            status_code=403,
            error_code="AUTHORIZATION_ERROR",
        )


class RateLimitError(TrafficAPIError):
    """Raised when rate limit is exceeded."""

    def __init__(self, limit: int = 100, period: int = 60):
        super().__init__(
            message=f"Rate limit exceeded: {limit} requests per {period} seconds",
            status_code=429,
            error_code="RATE_LIMIT_ERROR",
            details={"limit": limit, "period": period},
        )


class InternalServerError(TrafficAPIError):
    """Raised for unexpected server errors."""

    def __init__(self, message: str = "Internal server error"):
        super().__init__(
            message=message,
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        )


# ── ERROR HANDLER ───────────────────────────────────────────────

def handle_error(error: Exception) -> Tuple[Dict[str, Any], int]:
    """
    Convert an exception to a standardized error response.

    Parameters
    ----------
    error : Exception
        The exception that was raised.

    Returns
    -------
    tuple
        (response_dict, status_code)
    """
    if isinstance(error, TrafficAPIError):
        return (
            {
                "success": False,
                "timestamp": datetime.utcnow().isoformat(),
                "error_code": error.error_code,
                "message": error.message,
                "details": error.details,
            },
            error.status_code,
        )

    # Generic exception
    return (
        {
            "success": False,
            "timestamp": datetime.utcnow().isoformat(),
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred",
            "details": {"error": str(error)},
        },
        500,
    )
