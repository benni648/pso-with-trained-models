"""
Standardized API response formatting.

All API responses follow a consistent structure:
  - success: bool
  - timestamp: ISO format
  - message: human-readable description
  - data/error: payload
  - meta: optional pagination metadata
"""

from datetime import datetime
from typing import Dict, Any, List, Optional


class APIResponse:
    """
    Static class for building standardized API responses.

    Usage:
        return APIResponse.success(data={"key": "value"}, message="Done"), 200
        return APIResponse.error("ERROR_CODE", "Something went wrong"), 400
    """

    @staticmethod
    def success(
        data: Any = None,
        message: str = "Operation successful",
        meta: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Build a success response.

        Returns: {"success": true, "timestamp": "...", "message": "...", "data": {...}}
        """
        response = {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "message": message,
        }

        if data is not None:
            response["data"] = data

        if meta is not None:
            response["meta"] = meta

        return response

    @staticmethod
    def error(
        error_code: str,
        message: str,
        details: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Build an error response.

        Returns: {"success": false, "timestamp": "...", "error_code": "...", "message": "...", "details": {...}}
        """
        response = {
            "success": False,
            "timestamp": datetime.utcnow().isoformat(),
            "error_code": error_code,
            "message": message,
        }

        if details is not None:
            response["details"] = details

        return response

    @staticmethod
    def paginated(
        data: List,
        total: int,
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
        """
        Build a paginated response.

        Returns: {"success": true, "timestamp": "...", "data": [...], "meta": {"page": ..., "total": ..., "pages": ...}}
        """
        pages = (total + per_page - 1) // per_page if per_page > 0 else 0

        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
            "meta": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": pages,
            },
        }

    @staticmethod
    def predict_response(
        prediction: Dict,
        input_data: Dict,
        model_info: Dict,
    ) -> Dict[str, Any]:
        """Build a prediction-specific response."""
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Prediction successful",
            "data": {
                "prediction": prediction,
                "model_info": model_info,
                "input": input_data,
            },
        }

    @staticmethod
    def optimize_response(
        signal_timings: Dict,
        fitness: float,
        input_data: Dict,
    ) -> Dict[str, Any]:
        """Build an optimization-specific response."""
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Optimization successful",
            "data": {
                "signal_timings": signal_timings,
                "fitness": fitness,
                "input": input_data,
            },
        }

    @staticmethod
    def predict_and_optimize_response(
        prediction: Dict,
        signal_timings: Dict,
        fitness: float,
        input_data: Dict,
    ) -> Dict[str, Any]:
        """Build a combined prediction + optimization response."""
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Prediction and optimization successful",
            "data": {
                "prediction": prediction,
                "signal_timings": signal_timings,
                "fitness": fitness,
                "input": input_data,
            },
        }

    @staticmethod
    def health_response(health_data: Dict) -> Dict[str, Any]:
        """Build a health check response."""
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Health check completed",
            "data": health_data,
        }
