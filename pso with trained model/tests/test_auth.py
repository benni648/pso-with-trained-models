"""
Authentication and authorization tests.

Tests login, logout, refresh, role enforcement, and permission checks.
"""

import pytest


class TestLogin:
    """Test POST /login endpoint."""

    def test_login_success(self, client):
        """Valid credentials should return tokens."""
        response = client.post("/login", json={
            "email": "admin@pso.com",
            "password": "admin123",
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
        assert data["data"]["user"]["role"] == "ADMIN"

    def test_login_invalid_credentials(self, client):
        """Wrong password should return 401."""
        response = client.post("/login", json={
            "email": "admin@pso.com",
            "password": "wrongpassword",
        })
        assert response.status_code == 401

    def test_login_missing_fields(self, client):
        """Missing email/password should return 400."""
        response = client.post("/login", json={"email": "admin@pso.com"})
        assert response.status_code in [400, 422]

    def test_login_empty_email(self, client):
        """Empty email should return error."""
        response = client.post("/login", json={
            "email": "",
            "password": "admin123",
        })
        assert response.status_code in [400, 401]

    def test_login_empty_password(self, client):
        """Empty password should return error."""
        response = client.post("/login", json={
            "email": "admin@pso.com",
            "password": "",
        })
        assert response.status_code in [400, 401]


class TestLogout:
    """Test POST /logout endpoint."""

    def test_logout_success(self, client, admin_token):
        """Logged-in user should be able to logout."""
        response = client.post("/logout", headers={
            "Authorization": f"Bearer {admin_token}",
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_logout_without_token(self, client):
        """Logout without token should fail."""
        response = client.post("/logout")
        assert response.status_code == 401


class TestRefresh:
    """Test POST /refresh endpoint."""

    def test_refresh_token_success(self, client, admin_token):
        """Valid refresh token should return new access token."""
        # First login to get refresh token
        login_resp = client.post("/login", json={
            "email": "admin@pso.com",
            "password": "admin123",
        })
        refresh_token = login_resp.get_json()["data"]["refresh_token"]

        response = client.post("/refresh", json={
            "refresh_token": refresh_token,
        })
        assert response.status_code == 200
        data = response.get_json()
        assert "access_token" in data["data"]

    def test_refresh_token_invalid(self, client):
        """Invalid refresh token should return 401."""
        response = client.post("/refresh", json={
            "refresh_token": "invalid.token.here",
        })
        assert response.status_code == 401

    def test_refresh_token_missing(self, client):
        """Missing refresh token should return 400."""
        response = client.post("/refresh", json={})
        assert response.status_code in [400, 401]


class TestRoleEnforcement:
    """Test role-based access control."""

    def test_admin_access_protected_route(self, client, admin_token):
        """Admin should access protected routes."""
        response = client.post("/api/predict", headers={
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json",
        }, json={
            "time_step": 45,
            "hour": 8,
            "density": 0.72,
            "avg_wait_time": 38.5,
            "congestion_level": "HIGH",
        })
        # Should not be 403
        assert response.status_code != 403

    def test_viewer_cannot_optimize(self, client, viewer_token):
        """Viewer should not access optimize endpoint."""
        response = client.post("/api/optimize", headers={
            "Authorization": f"Bearer {viewer_token}",
            "Content-Type": "application/json",
        }, json={
            "north_vehicles": 4.55,
            "south_vehicles": 4.35,
            "east_vehicles": 4.31,
            "west_vehicles": 4.34,
        })
        assert response.status_code == 403

    def test_operator_can_optimize(self, client, operator_token):
        """Operator should access optimize endpoint."""
        response = client.post("/api/optimize", headers={
            "Authorization": f"Bearer {operator_token}",
            "Content-Type": "application/json",
        }, json={
            "north_vehicles": 4.55,
            "south_vehicles": 4.35,
            "east_vehicles": 4.31,
            "west_vehicles": 4.34,
        })
        assert response.status_code != 403

    def test_unauthenticated_access_denied(self, client):
        """Unauthenticated request should be rejected."""
        response = client.post("/api/predict", json={
            "time_step": 45,
            "hour": 8,
            "density": 0.72,
            "avg_wait_time": 38.5,
            "congestion_level": "HIGH",
        })
        assert response.status_code == 401

    def test_expired_token_rejected(self, client):
        """Expired token should be rejected."""
        response = client.post("/api/predict", headers={
            "Authorization": "Bearer expired.invalid.token",
            "Content-Type": "application/json",
        }, json={
            "time_step": 45,
            "hour": 8,
            "density": 0.72,
            "avg_wait_time": 38.5,
            "congestion_level": "HIGH",
        })
        assert response.status_code == 401

    def test_role_based_permissions(self, client, viewer_token):
        """Viewer role should only have predict permission."""
        # Should succeed (predict is allowed for viewer)
        response = client.post("/api/predict", headers={
            "Authorization": f"Bearer {viewer_token}",
            "Content-Type": "application/json",
        }, json={
            "time_step": 45,
            "hour": 8,
            "density": 0.72,
            "avg_wait_time": 38.5,
            "congestion_level": "HIGH",
        })
        assert response.status_code != 403
