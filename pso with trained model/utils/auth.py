"""
JWT Authentication and Role-Based Access Control (RBAC).

Features:
  - JWT token generation and verification
  - Access + refresh token flow
  - Three user roles: ADMIN, TRAFFIC_OPERATOR, VIEWER
  - Permission-based endpoint protection via decorators
"""

import os
import time
import uuid
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Any, Optional, List

from flask import request, g

from utils.errors import AuthenticationError, AuthorizationError
from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


# ── JWT SETTINGS ────────────────────────────────────────────────

try:
    from config.config import config
    JWT_SECRET = config.JWT_SECRET_KEY
    JWT_ALGORITHM = config.JWT_ALGORITHM
    ACCESS_EXPIRY = config.JWT_ACCESS_TOKEN_EXPIRES
    REFRESH_EXPIRY = config.JWT_REFRESH_TOKEN_EXPIRES
    JWT_ENABLED = config.JWT_ENABLED
except ImportError:
    JWT_SECRET = os.getenv("JWT_SECRET_KEY", "jwt-secret-key-change-in-production")
    JWT_ALGORITHM = "HS256"
    ACCESS_EXPIRY = timedelta(hours=24)
    REFRESH_EXPIRY = timedelta(days=30)
    JWT_ENABLED = os.getenv("JWT_ENABLED", "True").lower() == "true"


# ── DEFAULT USERS (in-memory) ──────────────────────────────────

DEMO_USERS = {
    "admin@pso.com": {
        "user_id": 1,
        "email": "admin@pso.com",
        "password": "admin123",
        "role": "ADMIN",
        "name": "System Admin",
    },
    "operator@pso.com": {
        "user_id": 2,
        "email": "operator@pso.com",
        "password": "operator123",
        "role": "TRAFFIC_OPERATOR",
        "name": "Traffic Operator",
    },
    "viewer@pso.com": {
        "user_id": 3,
        "email": "viewer@pso.com",
        "password": "viewer123",
        "role": "VIEWER",
        "name": "Viewer",
    },
}


# ── ROLE → PERMISSIONS MAPPING ──────────────────────────────────

try:
    from config.config import config as _config
    ROLE_PERMISSIONS = _config.ROLES
except (ImportError, AttributeError):
    ROLE_PERMISSIONS = {
        "ADMIN": ["predict", "optimize", "settings", "reports", "users"],
        "TRAFFIC_OPERATOR": ["predict", "optimize"],
        "VIEWER": ["predict"],
    }


# ── REVOKED TOKENS (in-memory) ─────────────────────────────────

_revoked_tokens = set()


# ── AUTH MANAGER ────────────────────────────────────────────────

class AuthManager:
    """
    Handles JWT token generation, verification, and user authentication.

    Usage:
        result = AuthManager.login("admin@pso.com", "admin123")
        # Returns: {"access_token": "eyJ...", "refresh_token": "eyJ...", "user": {...}}
    """

    @staticmethod
    def login(email: str, password: str) -> Dict[str, Any]:
        """
        Authenticate user and return JWT tokens.

        Parameters
        ----------
        email : str
            User email address.
        password : str
            User password.

        Returns
        -------
        dict
            Contains access_token, refresh_token, token_type, and user info.

        Raises
        ------
        AuthenticationError
            If credentials are invalid.
        """
        import jwt

        user = DEMO_USERS.get(email)

        if not user or user["password"] != password:
            logger.warning(f"Failed login attempt for: {email}")
            raise AuthenticationError("Invalid email or password")

        now = datetime.utcnow()

        # Access token payload
        access_payload = {
            "user_id": user["user_id"],
            "email": user["email"],
            "role": user["role"],
            "name": user["name"],
            "type": "access",
            "jti": uuid.uuid4().hex,
            "iat": now,
            "exp": now + ACCESS_EXPIRY,
        }

        # Refresh token payload
        refresh_payload = {
            "user_id": user["user_id"],
            "email": user["email"],
            "type": "refresh",
            "jti": uuid.uuid4().hex,
            "iat": now,
            "exp": now + REFRESH_EXPIRY,
        }

        access_token = jwt.encode(access_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        refresh_token = jwt.encode(refresh_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        logger.info(f"User logged in: {email} ({user['role']})")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": int(ACCESS_EXPIRY.total_seconds()),
            "user": {
                "user_id": user["user_id"],
                "email": user["email"],
                "role": user["role"],
                "name": user["name"],
            },
        }

    @staticmethod
    def logout(token: str):
        """
        Invalidate a token by adding it to the revoked set.

        Parameters
        ----------
        token : str
            The JWT token to revoke.
        """
        _revoked_tokens.add(token)
        logger.info("User logged out")

    @staticmethod
    def refresh_token(refresh_token: str) -> Dict[str, Any]:
        """
        Generate a new access token using a refresh token.

        Parameters
        ----------
        refresh_token : str
            The refresh JWT token.

        Returns
        -------
        dict
            Contains new access_token.

        Raises
        ------
        AuthenticationError
            If refresh token is invalid or expired.
        """
        import jwt

        try:
            payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Refresh token has expired")
        except (jwt.InvalidTokenError, ValueError, TypeError):
            raise AuthenticationError("Invalid refresh token")

        if refresh_token in _revoked_tokens:
            raise AuthenticationError("Refresh token has been revoked")

        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type")

        user = DEMO_USERS.get(payload.get("email"))
        if not user:
            raise AuthenticationError("User not found")

        now = datetime.utcnow()
        access_payload = {
            "user_id": user["user_id"],
            "email": user["email"],
            "role": user["role"],
            "name": user["name"],
            "type": "access",
            "jti": uuid.uuid4().hex,
            "iat": now,
            "exp": now + ACCESS_EXPIRY,
        }

        new_access_token = jwt.encode(access_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        logger.info(f"Token refreshed for: {user['email']}")

        return {
            "access_token": new_access_token,
            "token_type": "Bearer",
            "expires_in": int(ACCESS_EXPIRY.total_seconds()),
        }

    @staticmethod
    def get_token_from_request() -> Optional[str]:
        """
        Extract Bearer token from the Authorization header.

        Returns
        -------
        str or None
            The JWT token, or None if not present.
        """
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        return None

    @staticmethod
    def verify_token(token: str) -> Dict[str, Any]:
        """
        Decode and verify a JWT token.

        Parameters
        ----------
        token : str
            The JWT token to verify.

        Returns
        -------
        dict
            Decoded token payload.

        Raises
        ------
        AuthenticationError
            If token is invalid, expired, or revoked.
        """
        import jwt

        if token in _revoked_tokens:
            raise AuthenticationError("Token has been revoked")

        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except (jwt.InvalidTokenError, ValueError, TypeError):
            raise AuthenticationError("Invalid token")

        if payload.get("type") != "access":
            raise AuthenticationError("Invalid token type")

        return payload


# ── ROLE MANAGER ────────────────────────────────────────────────

class RoleManager:
    """
    Role-based access control decorators.

    Usage:
        @RoleManager.require_role("ADMIN")
        def admin_only(): ...

        @RoleManager.require_permission("optimize")
        def optimize(): ...
    """

    @staticmethod
    def require_role(*allowed_roles: str):
        """
        Decorator that checks if the user has one of the allowed roles.

        Parameters
        ----------
        *allowed_roles : str
            Role names that are allowed (e.g., "ADMIN", "TRAFFIC_OPERATOR").
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if not JWT_ENABLED:
                    return f(*args, **kwargs)

                token = AuthManager.get_token_from_request()
                if not token:
                    raise AuthenticationError("Authorization token required")

                payload = AuthManager.verify_token(token)
                user_role = payload.get("role", "")

                if user_role not in allowed_roles:
                    raise AuthorizationError(
                        f"Required role: {' or '.join(allowed_roles)}. Your role: {user_role}"
                    )

                # Attach user to request context
                g.user = {
                    "user_id": payload.get("user_id"),
                    "email": payload.get("email"),
                    "role": payload.get("role"),
                    "name": payload.get("name"),
                }

                return f(*args, **kwargs)
            return decorated_function
        return decorator

    @staticmethod
    def require_permission(permission: str):
        """
        Decorator that checks if the user's role has the required permission.

        Parameters
        ----------
        permission : str
            Permission name (e.g., "predict", "optimize", "settings").
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if not JWT_ENABLED:
                    return f(*args, **kwargs)

                token = AuthManager.get_token_from_request()
                if not token:
                    raise AuthenticationError("Authorization token required")

                payload = AuthManager.verify_token(token)
                user_role = payload.get("role", "")
                user_permissions = ROLE_PERMISSIONS.get(user_role, [])

                if permission not in user_permissions:
                    raise AuthorizationError(
                        f"Permission '{permission}' required. Your role: {user_role}"
                    )

                # Attach user to request context
                g.user = {
                    "user_id": payload.get("user_id"),
                    "email": payload.get("email"),
                    "role": payload.get("role"),
                    "name": payload.get("name"),
                }

                return f(*args, **kwargs)
            return decorated_function
        return decorator

    @staticmethod
    def get_user_from_token(token: str) -> Dict[str, Any]:
        """
        Extract user info from a JWT token.

        Parameters
        ----------
        token : str
            The JWT token.

        Returns
        -------
        dict
            User info: {user_id, email, role, name}.
        """
        payload = AuthManager.verify_token(token)
        return {
            "user_id": payload.get("user_id"),
            "email": payload.get("email"),
            "role": payload.get("role"),
            "name": payload.get("name"),
        }
