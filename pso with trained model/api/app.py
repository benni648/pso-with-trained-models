"""
=====================================================================
 PSO Smart Traffic Signal Optimization — Professional Flask API
=====================================================================
 Complete backend with JWT auth, role management, logging, health
 monitoring, reporting, and comprehensive API documentation.

 Endpoints:
   Authentication:
     POST   /login                 → Authenticate and get JWT token
     POST   /logout                → Logout
     POST   /refresh               → Refresh access token
   
   Traffic Operations:
     POST   /api/predict           → Traffic prediction
     POST   /api/optimize          → Signal optimization
     POST   /api/predict-and-optimize → Both in one call
   
   Information:
     GET    /api/health            → Server health status
     GET    /api/settings          → Get current settings
     POST   /api/settings          → Update settings (admin only)
   
   Reports:
     POST   /api/generate-report   → Generate traffic report
     GET    /api/reports           → List recent reports
   
   Documentation:
     GET    /docs                  → API documentation (Swagger)
     GET    /docs/json             → OpenAPI spec

 Run:
   python app.py

=====================================================================
"""

import logging
import sys
import os
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Any, Tuple

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flasgger import Swagger
import psutil

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))

# Import configuration and utilities
from config.config import config
from utils.logger import LoggerManager
from utils.response import APIResponse
from utils.errors import TrafficAPIError, handle_error
from utils.auth import AuthManager, RoleManager
from utils.health import HealthMonitor

# Import services
from services.prediction_service import PredictionService
from services.optimization_service import OptimizationService
from services.report_service import ReportGenerator
from services.settings_service import SettingsManager

# Phase 2: Enterprise services
try:
    from database import init_db, get_db
    from services.storage_service import StorageService
    from services.audit_service import AuditService
    from services.analytics_service import AnalyticsService
    from services.cache_service import CacheService
    from events import EventBus, PredictionCreatedEvent, OptimizationCompletedEvent
    PHASE_2_ENABLED = True
    logger_init = LoggerManager.get_logger('phase2_init')
    logger_init.info("✓ Phase 2 enterprise modules loaded")
except ImportError as e:
    logger_init = LoggerManager.get_logger('phase2_init')
    logger_init.warning(f"Phase 2 modules not fully available: {str(e)}")
    PHASE_2_ENABLED = False

# ──────────────────────────────────────────────
# INITIALIZE LOGGER
# ──────────────────────────────────────────────
logger = LoggerManager.get_logger(__name__)
logger.info("=" * 70)
logger.info(f"Starting {config.APP_NAME} v{config.APP_VERSION}")
logger.info(f"Environment: {config.ENVIRONMENT} | Debug: {config.DEBUG}")
logger.info("=" * 70)

# ──────────────────────────────────────────────
# FLASK APP SETUP
# ──────────────────────────────────────────────
app = Flask(__name__, static_folder="frontend", static_url_path="/")

# Configure app
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["JSON_SORT_KEYS"] = False

# Enable CORS
CORS(
    app,
    resources={r"/api/*": {"origins": config.CORS_ORIGINS}},
    supports_credentials=config.CORS_ALLOW_CREDENTIALS,
    allow_headers=config.CORS_ALLOW_HEADERS,
    expose_headers=config.CORS_EXPOSE_HEADERS,
    methods=config.CORS_METHODS,
)

logger.info(f"CORS enabled for origins: {config.CORS_ORIGINS}")

# ──────────────────────────────────────────────
# SWAGGER/OPENAPI DOCUMENTATION
# ──────────────────────────────────────────────
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/docs",
}

swagger = Swagger(app, config=swagger_config)

logger.info("Swagger/OpenAPI documentation enabled at /docs")

# ──────────────────────────────────────────────
# INITIALIZE SERVICES
# ──────────────────────────────────────────────
try:
    prediction_service = PredictionService()
    logger.info("PredictionService initialized")
except Exception as e:
    logger.error(f"Failed to initialize PredictionService: {str(e)}")
    prediction_service = None

try:
    optimization_service = OptimizationService()
    logger.info("OptimizationService initialized")
except Exception as e:
    logger.error(f"Failed to initialize OptimizationService: {str(e)}")
    optimization_service = None

try:
    report_generator = ReportGenerator()
    logger.info("ReportGenerator initialized")
except Exception as e:
    logger.error(f"Failed to initialize ReportGenerator: {str(e)}")
    report_generator = None

try:
    settings_manager = SettingsManager()
    logger.info("SettingsManager initialized")
except Exception as e:
    logger.error(f"Failed to initialize SettingsManager: {str(e)}")
    settings_manager = None

try:
    health_monitor = HealthMonitor()
    logger.info("HealthMonitor initialized")
except Exception as e:
    logger.error(f"Failed to initialize HealthMonitor: {str(e)}")
    health_monitor = None

# ──────────────────────────────────────────────
# MIDDLEWARE
# ──────────────────────────────────────────────
@app.before_request
def before_request():
    """Pre-request processing."""
    request.start_time = datetime.now()
    logger.debug(f"{request.method} {request.path}")


@app.after_request
def after_request(response):
    """Post-request processing."""
    if hasattr(request, "start_time"):
        duration = (datetime.now() - request.start_time).total_seconds()
        logger.debug(f"{request.method} {request.path} -> {response.status_code} ({duration:.3f}s)")
    return response


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    logger.warning(f"404 Not Found: {request.path}")
    return (
        APIResponse.error(
            "NOT_FOUND",
            f"Endpoint {request.path} not found",
            {"path": request.path}
        ),
        404,
    )


@app.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors."""
    logger.warning(f"405 Method Not Allowed: {request.method} {request.path}")
    return (
        APIResponse.error(
            "METHOD_NOT_ALLOWED",
            f"Method {request.method} not allowed for {request.path}",
        ),
        405,
    )


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"500 Internal Server Error: {str(error)}")
    return (
        APIResponse.error(
            "INTERNAL_SERVER_ERROR",
            "An unexpected error occurred",
        ),
        500,
    )


# ──────────────────────────────────────────────
# AUTHENTICATION ROUTES
# ──────────────────────────────────────────────
@app.route("/login", methods=["POST"])
def login():
    """
    Authenticate user and get JWT token.

    ---
    tags:
      - Authentication
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            email:
              type: string
              example: admin@pso.com
            password:
              type: string
              example: admin123
    responses:
      200:
        description: Login successful
        schema:
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                access_token:
                  type: string
                refresh_token:
                  type: string
                token_type:
                  type: string
                user:
                  type: object
      401:
        description: Invalid credentials
    """
    if not config.JWT_ENABLED:
        return APIResponse.error("JWT_DISABLED", "Authentication is disabled"), 403

    try:
        data = request.get_json()
        if not data:
            return APIResponse.error("INVALID_JSON", "Request body must be valid JSON"), 400

        email = data.get("email", "").strip()
        password = data.get("password", "")

        if not email or not password:
            return APIResponse.error("MISSING_FIELD", "Email and password are required"), 400

        result = AuthManager.login(email, password)
        return APIResponse.success(data=result, message="Login successful"), 200

    except TrafficAPIError as error:
        response_data, status_code = handle_error(error)
        return response_data, status_code
    except Exception as e:
        logger.exception(f"Login error: {str(e)}")
        response_data, status_code = handle_error(e)
        return response_data, status_code


@app.route("/logout", methods=["POST"])
@RoleManager.require_role("ADMIN", "TRAFFIC_OPERATOR", "VIEWER")
def logout():
    """
    Logout user.

    ---
    tags:
      - Authentication
    security:
      - Bearer: []
    responses:
      200:
        description: Logout successful
      401:
        description: Unauthorized
    """
    token = AuthManager.get_token_from_request()
    AuthManager.logout(token)
    return APIResponse.success(message="Logout successful"), 200


@app.route("/refresh", methods=["POST"])
def refresh():
    """
    Refresh access token using refresh token.

    ---
    tags:
      - Authentication
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            refresh_token:
              type: string
    responses:
      200:
        description: Token refreshed successfully
      401:
        description: Invalid refresh token
    """
    if not config.JWT_ENABLED:
        return APIResponse.error("JWT_DISABLED", "Authentication is disabled"), 403

    try:
        data = request.get_json()
        refresh_token = data.get("refresh_token", "")

        if not refresh_token:
            return APIResponse.error("MISSING_FIELD", "refresh_token is required"), 400

        result = AuthManager.refresh_token(refresh_token)
        return APIResponse.success(data=result, message="Token refreshed successfully"), 200

    except TrafficAPIError as error:
        response_data, status_code = handle_error(error)
        return response_data, status_code


# ──────────────────────────────────────────────
# TRAFFIC PREDICTION & OPTIMIZATION ROUTES
# ──────────────────────────────────────────────
@app.route("/api/predict", methods=["POST"])
@RoleManager.require_permission("predict")
def predict():
    """
    Predict next traffic state.

    ---
    tags:
      - Traffic Operations
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            time_step:
              type: integer
              example: 45
            hour:
              type: integer
              example: 8
            density:
              type: number
              example: 0.72
            avg_wait_time:
              type: number
              example: 38.5
            congestion_level:
              type: string
              enum: [LOW, MEDIUM, HIGH]
              example: HIGH
    responses:
      200:
        description: Prediction successful
      400:
        description: Invalid input
      401:
        description: Unauthorized
      422:
        description: Invalid field values
      500:
        description: Prediction failed
    """
    if not prediction_service:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE",
            "Prediction service is not available"
        ), 503

    try:
        data = request.get_json()
        if not data:
            return APIResponse.error("INVALID_JSON", "Request body must be valid JSON"), 400

        result = prediction_service.predict(data)
        model_info = prediction_service.get_model_info()

        return APIResponse.predict_response(result, data, model_info), 200

    except TrafficAPIError as error:
        response_data, status_code = handle_error(error)
        return response_data, status_code
    except Exception as e:
        logger.exception(f"Prediction error: {str(e)}")
        response_data, status_code = handle_error(e)
        return response_data, status_code


@app.route("/api/optimize", methods=["POST"])
@RoleManager.require_permission("optimize")
def optimize():
    """
    Optimize traffic signal timings.

    ---
    tags:
      - Traffic Operations
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            north_vehicles:
              type: number
            south_vehicles:
              type: number
            east_vehicles:
              type: number
            west_vehicles:
              type: number
    responses:
      200:
        description: Optimization successful
      400:
        description: Invalid input
      401:
        description: Unauthorized
      500:
        description: Optimization failed
    """
    if not optimization_service:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE",
            "Optimization service is not available"
        ), 503

    try:
        data = request.get_json()
        if not data:
            return APIResponse.error("INVALID_JSON", "Request body must be valid JSON"), 400

        result = optimization_service.optimize(data)
        fitness = result.get("fitness", 0)
        signal_timings = {k: v for k, v in result.items() if k != "fitness"}

        return APIResponse.optimize_response(signal_timings, fitness, data), 200

    except TrafficAPIError as error:
        response_data, status_code = handle_error(error)
        return response_data, status_code
    except Exception as e:
        logger.exception(f"Optimization error: {str(e)}")
        response_data, status_code = handle_error(e)
        return response_data, status_code


@app.route("/api/predict-and-optimize", methods=["POST"])
@RoleManager.require_permission("optimize")
def predict_and_optimize():
    """
    Predict traffic and optimize signal timings in one call.

    ---
    tags:
      - Traffic Operations
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            time_step:
              type: integer
            hour:
              type: integer
            density:
              type: number
            avg_wait_time:
              type: number
            congestion_level:
              type: string
    responses:
      200:
        description: Prediction and optimization successful
      400:
        description: Invalid input
      401:
        description: Unauthorized
      422:
        description: Invalid field values
      500:
        description: Operation failed
    """
    if not prediction_service or not optimization_service:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE",
            "Required services are not available"
        ), 503

    try:
        data = request.get_json()
        if not data:
            return APIResponse.error("INVALID_JSON", "Request body must be valid JSON"), 400

        prediction = prediction_service.predict(data)
        optimization = optimization_service.optimize(prediction)
        fitness = optimization.get("fitness", 0)
        signal_timings = {k: v for k, v in optimization.items() if k != "fitness"}

        return APIResponse.predict_and_optimize_response(
            prediction, signal_timings, fitness, data
        ), 200

    except TrafficAPIError as error:
        response_data, status_code = handle_error(error)
        return response_data, status_code
    except Exception as e:
        logger.exception(f"Predict-and-optimize error: {str(e)}")
        response_data, status_code = handle_error(e)
        return response_data, status_code


# ──────────────────────────────────────────────
# HEALTH & INFORMATION ROUTES
# ──────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    """
    Get server health status.

    ---
    tags:
      - Information
    responses:
      200:
        description: Health status
        schema:
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                server_status:
                  type: string
                model_loaded:
                  type: boolean
                uptime:
                  type: string
                memory_usage:
                  type: object
                cpu_usage:
                  type: object
    """
    try:
        health_data = health_monitor.get_system_health() if health_monitor else {}

        return APIResponse.success(
            data=health_data,
            message="Server health check completed"
        ), 200

    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return APIResponse.error(
            "HEALTH_CHECK_FAILED",
            f"Health check failed: {str(e)}"
        ), 500


# ──────────────────────────────────────────────
# SETTINGS ROUTES
# ──────────────────────────────────────────────
@app.route("/api/settings", methods=["GET"])
def get_settings():
    """
    Get current application settings.

    ---
    tags:
      - Settings
    responses:
      200:
        description: Current settings
    """
    if not settings_manager:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE",
            "Settings service is not available"
        ), 503

    try:
        settings = settings_manager.get_all_settings()
        return APIResponse.success(data=settings, message="Settings retrieved"), 200

    except Exception as e:
        logger.exception(f"Get settings error: {str(e)}")
        return APIResponse.error(
            "SETTINGS_ERROR",
            f"Failed to get settings: {str(e)}"
        ), 500


@app.route("/api/settings", methods=["POST"])
@RoleManager.require_role("ADMIN")
def update_settings():
    """
    Update application settings (admin only).

    ---
    tags:
      - Settings
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            pso_iterations:
              type: integer
            pso_particles:
              type: integer
            simulation_speed:
              type: number
    responses:
      200:
        description: Settings updated
      400:
        description: Invalid settings
      403:
        description: Forbidden
    """
    if not settings_manager:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE",
            "Settings service is not available"
        ), 503

    try:
        data = request.get_json()
        if not data:
            return APIResponse.error("INVALID_JSON", "Request body must be valid JSON"), 400

        # Validate settings before updating
        for key, value in data.items():
            if not settings_manager.validate_setting(key, value):
                return APIResponse.error(
                    "INVALID_SETTING",
                    f"Invalid value for setting '{key}': {value}"
                ), 400

        updated_settings = settings_manager.update_settings(data)
        logger.info(f"Settings updated by {request.user['email']}: {list(data.keys())}")

        return APIResponse.success(
            data=updated_settings,
            message="Settings updated successfully"
        ), 200

    except Exception as e:
        logger.exception(f"Update settings error: {str(e)}")
        return APIResponse.error(
            "SETTINGS_ERROR",
            f"Failed to update settings: {str(e)}"
        ), 500


# ──────────────────────────────────────────────
# REPORT ROUTES
# ──────────────────────────────────────────────
@app.route("/api/generate-report", methods=["POST"])
@RoleManager.require_role("ADMIN", "TRAFFIC_OPERATOR")
def generate_report():
    """
    Generate traffic report.

    ---
    tags:
      - Reports
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            title:
              type: string
            format:
              type: string
              enum: [json, csv, pdf]
    responses:
      200:
        description: Report generated
      403:
        description: Forbidden
    """
    if not report_generator:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE",
            "Report service is not available"
        ), 503

    try:
        data = request.get_json() or {}
        title = data.get("title", "Traffic Report")
        report_format = data.get("format", "json")

        # Generate report with dummy data
        report_path = report_generator.generate_traffic_report(
            title=title,
            predictions=[],
            optimizations=[],
            statistics={"avg_congestion": 0.5, "avg_wait_time": 30},
            format=report_format
        )

        logger.info(f"Report generated by {request.user['email']}: {report_path}")

        return APIResponse.success(
            data={"path": report_path, "format": report_format},
            message="Report generated successfully"
        ), 200

    except Exception as e:
        logger.exception(f"Report generation error: {str(e)}")
        return APIResponse.error(
            "REPORT_ERROR",
            f"Failed to generate report: {str(e)}"
        ), 500


@app.route("/api/reports", methods=["GET"])
@RoleManager.require_role("ADMIN", "TRAFFIC_OPERATOR")
def list_reports():
    """
    List recent reports.

    ---
    tags:
      - Reports
    security:
      - Bearer: []
    responses:
      200:
        description: List of reports
    """
    if not report_generator:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE",
            "Report service is not available"
        ), 503

    try:
        limit = request.args.get("limit", 10, type=int)
        reports = report_generator.get_recent_reports(limit)

        return APIResponse.success(
            data=reports,
            message=f"Retrieved {len(reports)} recent reports"
        ), 200

    except Exception as e:
        logger.exception(f"List reports error: {str(e)}")
        return APIResponse.error(
            "REPORT_ERROR",
            f"Failed to list reports: {str(e)}"
        ), 500


# ──────────────────────────────────────────────
# PHASE 2: ENTERPRISE ROUTES
# ──────────────────────────────────────────────
if PHASE_2_ENABLED:
    try:
        from api.enterprise_routes import enterprise_bp
        app.register_blueprint(enterprise_bp)
        logger.info("✓ Enterprise routes registered at /api/enterprise")
    except ImportError as e:
        logger.warning(f"Could not load enterprise routes: {str(e)}")


# ──────────────────────────────────────────────
# FRONTEND ROUTES
# ──────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    """Serve main dashboard."""
    try:
        return send_from_directory("frontend", "pso_traffic_dashboard_connected.html")
    except Exception:
        return "PSO Traffic Dashboard", 200


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
if __name__ == "__main__":
    # Phase 2: Initialize database
    if PHASE_2_ENABLED:
        try:
            init_db()
            logger.info("✓ Database initialized")
        except Exception as e:
            logger.warning(f"Database initialization skipped: {str(e)}")
    
    logger.info("=" * 70)
    logger.info(f"Starting server on {config.HOST}:{config.PORT}")
    logger.info(f"Dashboard: http://localhost:{config.PORT}")
    logger.info(f"API Docs: http://localhost:{config.PORT}/docs")
    logger.info(f"Login with: admin@pso.com / admin123")
    if PHASE_2_ENABLED:
        logger.info(f"Enterprise API: http://localhost:{config.PORT}/api/enterprise")
    logger.info("=" * 70)

    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
        use_reloader=config.DEBUG
    )
