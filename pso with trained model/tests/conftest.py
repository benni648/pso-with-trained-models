"""
Pytest fixtures and configuration.

Provides test client, auth tokens, and mock data for all tests.
"""

import sys
import os
import pytest

# Ensure project root is in Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


@pytest.fixture
def app():
    """Create Flask test application."""
    from api.app import app
    app.config["TESTING"] = True
    app.config["JWT_ENABLED"] = True
    return app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def admin_token(client):
    """Get admin JWT token."""
    response = client.post("/login", json={
        "email": "admin@pso.com",
        "password": "admin123",
    })
    data = response.get_json()
    return data.get("data", {}).get("access_token", "")


@pytest.fixture
def operator_token(client):
    """Get operator JWT token."""
    response = client.post("/login", json={
        "email": "operator@pso.com",
        "password": "operator123",
    })
    data = response.get_json()
    return data.get("data", {}).get("access_token", "")


@pytest.fixture
def viewer_token(client):
    """Get viewer JWT token."""
    response = client.post("/login", json={
        "email": "viewer@pso.com",
        "password": "viewer123",
    })
    data = response.get_json()
    return data.get("data", {}).get("access_token", "")


@pytest.fixture
def sample_prediction_data():
    """Valid prediction request body."""
    return {
        "time_step": 45,
        "hour": 8,
        "density": 0.72,
        "avg_wait_time": 38.5,
        "congestion_level": "HIGH",
    }


@pytest.fixture
def sample_optimization_data():
    """Valid optimization request body."""
    return {
        "north_vehicles": 4.55,
        "south_vehicles": 4.35,
        "east_vehicles": 4.31,
        "west_vehicles": 4.34,
    }
