"""
=====================================================================
 Configuration Management System
=====================================================================
 Centralized configuration for the entire PSO Traffic application.
 All hardcoded values are moved here for easy modification.
=====================================================================
"""

import os
from datetime import timedelta


class Config:
    """Base configuration - shared across all environments."""

    # ── APPLICATION ────────────────────────────
    APP_NAME = "PSO Traffic Signal Optimization"
    APP_VERSION = "1.0.0"
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    # ── SERVER ─────────────────────────────────
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 5000))
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

    # ── DATABASE & FILE PATHS ──────────────────
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_PATH = os.path.join(BASE_DIR, "pso_traffic_preprocessed.csv")
    MODEL_DIR = os.path.join(BASE_DIR, "saved_models")
    LOGS_DIR = os.path.join(BASE_DIR, "logs")
    REPORTS_DIR = os.path.join(BASE_DIR, "reports")

    # Ensure directories exist
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # ── LOGGING ────────────────────────────────
    LOG_FILE = os.path.join(LOGS_DIR, "app.log")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
    LOG_BACKUP_COUNT = 10

    # ── ML MODEL CONFIG ────────────────────────
    ML_MODEL_NAME = "rf_model.pkl"
    ML_BASELINE_NAME = "lr_model.pkl"
    ML_META_FILE = "model_meta.json"

    # Training parameters
    TEST_SIZE = 0.20
    RANDOM_SEED = 42
    RF_N_ESTIMATORS = 150
    RF_MAX_DEPTH = None
    RF_MIN_SAMPLES_SPLIT = 5

    # Features and targets
    FEATURES = ["time_step", "hour", "density", "avg_wait_time", "congestion_level_enc"]
    TARGETS = ["north_vehicles", "south_vehicles", "east_vehicles", "west_vehicles"]
    CONGESTION_MAP = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

    # ── PSO OPTIMIZER CONFIG ────────────────────
    PSO_N_PARTICLES = int(os.getenv("PSO_N_PARTICLES", 30))
    PSO_N_ITERATIONS = int(os.getenv("PSO_N_ITERATIONS", 50))
    PSO_BOUNDS_MIN = int(os.getenv("PSO_BOUNDS_MIN", 5))
    PSO_BOUNDS_MAX = int(os.getenv("PSO_BOUNDS_MAX", 60))
    PSO_INERTIA_WEIGHT = float(os.getenv("PSO_INERTIA_WEIGHT", 0.7))
    PSO_COGNITIVE_COEFF = float(os.getenv("PSO_COGNITIVE_COEFF", 1.5))
    PSO_SOCIAL_COEFF = float(os.getenv("PSO_SOCIAL_COEFF", 1.5))

    # ── CORS & SECURITY ────────────────────────
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
    CORS_ALLOW_CREDENTIALS = True
    CORS_ALLOW_HEADERS = ["Content-Type", "Authorization"]
    CORS_EXPOSE_HEADERS = ["Content-Type", "Authorization"]
    CORS_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]

    # ── JWT AUTHENTICATION ─────────────────────
    JWT_ENABLED = os.getenv("JWT_ENABLED", "True").lower() == "true"
    JWT_ALGORITHM = "HS256"
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret-key-change-in-production")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv("JWT_TOKEN_HOURS", 24)))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.getenv("JWT_REFRESH_TOKEN_DAYS", 30)))

    # ── USER ROLES & PERMISSIONS ───────────────
    ROLES = {
        "ADMIN": ["predict", "optimize", "settings", "reports", "users"],
        "TRAFFIC_OPERATOR": ["predict", "optimize"],
        "VIEWER": ["predict"],
    }

    # ── REPORT GENERATION ──────────────────────
    REPORT_FORMAT = os.getenv("REPORT_FORMAT", "pdf")  # pdf, csv, json
    REPORT_INCLUDE_CHARTS = True
    REPORT_INCLUDE_HISTORY = True

    # ── RATE LIMITING ──────────────────────────
    RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", 100))
    RATE_LIMIT_PERIOD = int(os.getenv("RATE_LIMIT_PERIOD", 60))  # seconds

    # ── CACHE ──────────────────────────────────
    CACHE_ENABLED = os.getenv("CACHE_ENABLED", "True").lower() == "true"
    CACHE_TTL = int(os.getenv("CACHE_TTL", 300))  # 5 minutes

    # ── MONITORING ─────────────────────────────
    ENABLE_METRICS = True
    ENABLE_HEALTH_CHECK = True
    HEALTH_CHECK_INTERVAL = 30  # seconds

    # ── SETTINGS ───────────────────────────────
    SETTINGS_FILE = os.path.join(BASE_DIR, "config", "settings.json")
    DEFAULT_SETTINGS = {
        "simulation_speed": 1.0,
        "pso_iterations": PSO_N_ITERATIONS,
        "pso_particles": PSO_N_PARTICLES,
        "model_selection": "rf_model.pkl",
        "logging_level": LOG_LEVEL,
        "enable_notifications": True,
        "enable_animations": True,
    }


class DevelopmentConfig(Config):
    """Development environment configuration."""

    DEBUG = True
    LOG_LEVEL = "DEBUG"
    CORS_ORIGINS = ["*"]


class ProductionConfig(Config):
    """Production environment configuration."""

    DEBUG = False
    LOG_LEVEL = "INFO"
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",")
    JWT_ENABLED = True


class TestingConfig(Config):
    """Testing environment configuration."""

    DEBUG = True
    LOG_LEVEL = "DEBUG"
    TESTING = True
    JWT_ENABLED = True
    RATE_LIMIT_ENABLED = False


def get_config(environment: str = None) -> Config:
    """
    Get configuration object based on environment.

    Parameters
    ----------
    environment : str, optional
        Environment name. Defaults to ENVIRONMENT env var.

    Returns
    -------
    Config
        Configuration object for the specified environment.
    """
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "development").lower()

    config_map = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": TestingConfig,
    }

    return config_map.get(environment, DevelopmentConfig)()


# Global config instance
config = get_config()
