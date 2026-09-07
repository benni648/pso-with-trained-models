"""
API endpoint tests.

Tests all major API endpoints for correct behavior.
"""

import pytest


class TestHealthEndpoint:
    """Test GET /api/health endpoint."""

    def test_health_endpoint(self, client):
        """Health endpoint should return 200."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True


class TestPredictEndpoint:
    """Test POST /api/predict endpoint."""

    def test_predict_success(self, client, admin_token, sample_prediction_data):
        """Valid prediction request should succeed."""
        response = client.post("/api/predict", headers={
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json",
        }, json=sample_prediction_data)
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_predict_missing_fields(self, client, admin_token):
        """Missing required fields should return error."""
        response = client.post("/api/predict", headers={
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json",
        }, json={"time_step": 45})
        assert response.status_code in [400, 422]

    def test_predict_invalid_congestion(self, client, admin_token):
        """Invalid congestion level should return error."""
        response = client.post("/api/predict", headers={
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json",
        }, json={
            "time_step": 45,
            "hour": 8,
            "density": 0.72,
            "avg_wait_time": 38.5,
            "congestion_level": "INVALID",
        })
        assert response.status_code == 422


class TestOptimizeEndpoint:
    """Test POST /api/optimize endpoint."""

    def test_optimize_success(self, client, admin_token, sample_optimization_data):
        """Valid optimization request should succeed."""
        response = client.post("/api/optimize", headers={
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json",
        }, json=sample_optimization_data)
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_optimize_missing_vehicles(self, client, admin_token):
        """Missing vehicle counts should return error."""
        response = client.post("/api/optimize", headers={
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json",
        }, json={"north_vehicles": 4.55})
        assert response.status_code in [400, 422]


class TestPredictAndOptimizeEndpoint:
    """Test POST /api/predict-and-optimize endpoint."""

    def test_predict_and_optimize_success(self, client, admin_token, sample_prediction_data):
        """Combined endpoint should return both prediction and optimization."""
        response = client.post("/api/predict-and-optimize", headers={
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json",
        }, json=sample_prediction_data)
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True


class TestSettingsEndpoints:
    """Test GET/POST /api/settings endpoints."""

    def test_get_settings(self, client):
        """Settings should be retrievable."""
        response = client.get("/api/settings")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_update_settings_admin(self, client, admin_token):
        """Admin should be able to update settings."""
        response = client.post("/api/settings", headers={
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json",
        }, json={"pso_iterations": 75})
        assert response.status_code == 200

    def test_update_settings_viewer_denied(self, client, viewer_token):
        """Viewer should not be able to update settings."""
        response = client.post("/api/settings", headers={
            "Authorization": f"Bearer {viewer_token}",
            "Content-Type": "application/json",
        }, json={"pso_iterations": 75})
        assert response.status_code == 403


class TestReportEndpoints:
    """Test report generation endpoints."""

    def test_generate_report(self, client, admin_token):
        """Admin should be able to generate reports."""
        response = client.post("/api/generate-report", headers={
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json",
        }, json={"title": "Test Report", "format": "json"})
        assert response.status_code == 200

    def test_list_reports(self, client, admin_token):
        """Should list recent reports."""
        response = client.get("/api/reports", headers={
            "Authorization": f"Bearer {admin_token}",
        })
        assert response.status_code == 200


class TestErrorHandlers:
    """Test error handling."""

    def test_404_handler(self, client):
        """Non-existent endpoint should return 404."""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404

    def test_swagger_docs_available(self, client):
        """Swagger docs should be accessible."""
        response = client.get("/docs")
        assert response.status_code == 200
