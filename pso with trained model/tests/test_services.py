"""
Service layer unit tests.

Tests individual services in isolation.
"""

import pytest


class TestPredictionService:
    """Test PredictionService."""

    def test_prediction_service_predict(self):
        """PredictionService should return valid predictions."""
        from services.prediction_service import PredictionService

        service = PredictionService()
        if not service.predictor:
            pytest.skip("Model not available")

        result = service.predict({
            "time_step": 45,
            "hour": 8,
            "density": 0.72,
            "avg_wait_time": 38.5,
            "congestion_level": "HIGH",
        })

        assert "north_vehicles" in result
        assert "south_vehicles" in result
        assert "east_vehicles" in result
        assert "west_vehicles" in result
        assert "total_vehicles" in result
        assert result["north_vehicles"] >= 0
        assert result["south_vehicles"] >= 0

    def test_prediction_service_invalid_input(self):
        """PredictionService should raise error for invalid input."""
        from services.prediction_service import PredictionService
        from utils.errors import MissingFieldError

        service = PredictionService()
        if not service.predictor:
            pytest.skip("Model not available")

        with pytest.raises(MissingFieldError):
            service.predict({"time_step": 45})


class TestOptimizationService:
    """Test OptimizationService."""

    def test_optimization_service_optimize(self):
        """OptimizationService should return valid signal timings."""
        from services.optimization_service import OptimizationService

        service = OptimizationService()
        if not service.optimizer:
            pytest.skip("PSO not available")

        result = service.optimize({
            "north_vehicles": 4.55,
            "south_vehicles": 4.35,
            "east_vehicles": 4.31,
            "west_vehicles": 4.34,
        })

        assert "north_green" in result
        assert "south_green" in result
        assert "east_green" in result
        assert "west_green" in result
        assert "fitness" in result
        assert result["fitness"] >= 0

    def test_optimization_service_zero_vehicles(self):
        """OptimizationService should handle zero vehicle counts."""
        from services.optimization_service import OptimizationService

        service = OptimizationService()
        if not service.optimizer:
            pytest.skip("PSO not available")

        result = service.optimize({
            "north_vehicles": 0,
            "south_vehicles": 0,
            "east_vehicles": 0,
            "west_vehicles": 0,
        })

        assert "fitness" in result


class TestReportService:
    """Test ReportGenerator."""

    def test_report_service_generate_json(self):
        """ReportGenerator should create JSON reports."""
        from services.report_service import ReportGenerator

        generator = ReportGenerator()
        filepath = generator.generate_traffic_report(
            title="Test JSON Report",
            statistics={"avg_congestion": 0.5},
            format="json",
        )

        assert filepath.endswith(".json")
        assert filepath is not None

        # Verify file exists
        import os
        assert os.path.exists(filepath)

    def test_report_service_generate_csv(self):
        """ReportGenerator should create CSV reports."""
        from services.report_service import ReportGenerator

        generator = ReportGenerator()
        filepath = generator.generate_traffic_report(
            title="Test CSV Report",
            format="csv",
        )

        assert filepath.endswith(".csv")

        import os
        assert os.path.exists(filepath)


class TestSettingsService:
    """Test SettingsManager."""

    def test_settings_service_get_all(self):
        """SettingsManager should return all settings."""
        from services.settings_service import SettingsManager

        manager = SettingsManager()
        settings = manager.get_all_settings()

        assert isinstance(settings, dict)
        assert "simulation_speed" in settings
        assert "pso_iterations" in settings

    def test_settings_service_validate(self):
        """SettingsManager should validate setting values."""
        from services.settings_service import SettingsManager

        manager = SettingsManager()

        # Valid values
        assert manager.validate_setting("pso_iterations", 100) is True
        assert manager.validate_setting("simulation_speed", 2.0) is True

        # Invalid values
        assert manager.validate_setting("pso_iterations", 5) is False  # Too low
        assert manager.validate_setting("pso_iterations", 600) is False  # Too high
        assert manager.validate_setting("unknown_key", "value") is False
