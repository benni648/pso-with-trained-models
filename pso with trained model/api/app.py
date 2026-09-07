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
   
   Camera (Phase 1):
     POST   /api/camera/start      → Start camera pipeline
     POST   /api/camera/stop       → Stop camera pipeline
     GET    /api/camera/status     → Pipeline status
     GET    /api/camera/frame      → MJPEG annotated frame stream
   
   Documentation:
     GET    /docs                  → API documentation (Swagger)
     GET    /docs/json             → OpenAPI spec

 Run:
   python app.py

=====================================================================
"""

import json
import logging
import sys
import os
import time
import threading
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Any, Tuple

from flask import Flask, request, jsonify, send_from_directory, g, Response
from flask_cors import CORS
from flasgger import Swagger
import psutil

# Add project root (parent of api/) to path so root-level packages
# (config, utils, services, ...) are importable when run directly:
#   python api/app.py
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

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

# Realtime (Phase 2): WebSocket live updates
try:
    from realtime.socket_manager import SocketManager
    from realtime.data_stream import DataStream
    REALTIME_ENABLED = True
except ImportError as e:
    logger_init = LoggerManager.get_logger('realtime_init')
    logger_init.warning(f"Realtime modules not fully available: {str(e)}")
    REALTIME_ENABLED = False


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
# Absolute paths: Flask resolves relative folders against the module
# directory (api/), which breaks when launched as `python api/app.py`.
STATIC_DIR = os.path.join(PROJECT_ROOT, "frontend")
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/")

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

# Phase 3: Prometheus metrics (no-op if prometheus-client is absent)
try:
    from monitoring import register_metrics
    register_metrics(app)
except ImportError:
    logger.warning("monitoring package unavailable — /metrics endpoint disabled")

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


@app.errorhandler(TrafficAPIError)
def handle_api_error(error):
    """
    Handle custom API errors raised anywhere in the request cycle
    (including inside auth decorators, which run before route bodies).

    Parameters
    ----------
    error : TrafficAPIError
        The custom exception that was raised.

    Returns
    -------
    tuple
        (response_data, status_code)
    """
    logger.warning(
        f"API error {error.status_code} {error.error_code}: {error.message}"
    )
    response_data, status_code = handle_error(error)
    return response_data, status_code


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
        logger.info(f"Settings updated by {g.user['email']}: {list(data.keys())}")

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

        logger.info(f"Report generated by {g.user['email']}: {report_path}")

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
# PHASE 1: CAMERA PIPELINE ROUTES
# ──────────────────────────────────────────────

# Global camera pipeline instance (managed via /api/camera/* endpoints)
camera_pipeline = None
camera_pipeline_lock = threading.Lock()


def _build_camera_pipeline(source=None, intersection_id=None):
    """
    Build a CameraPipeline from the default config with optional overrides.

    Parameters
    ----------
    source : str or int, optional
        Override camera source (RTSP URL, webcam index, or file path).
    intersection_id : str, optional
        Override intersection identifier.

    Returns
    -------
    CameraPipeline
        Configured pipeline instance (not yet started).

    Raises
    ------
    RuntimeError
        If vision dependencies are not installed.
    """
    from vision.config import CAMERA_CONFIG
    from vision.pipeline import CameraPipeline

    camera_config = json.loads(json.dumps(CAMERA_CONFIG))  # deep copy

    if source is not None:
        if isinstance(source, str) and source.isdigit():
            source = int(source)
        camera_config["cameras"][0]["source"] = source
    if intersection_id:
        camera_config["intersection_id"] = intersection_id

    has_pipeline_observers = (
        (REALTIME_ENABLED and socket_manager is not None and socket_manager.available)
        or intelligence_service is not None
    )
    return CameraPipeline(
        camera_config,
        prediction_service=prediction_service,
        optimization_service=optimization_service,
        emit_callback=_on_pipeline_result if has_pipeline_observers else None,
    )


@app.route("/api/camera/start", methods=["POST"])
@RoleManager.require_role("ADMIN", "TRAFFIC_OPERATOR")
def camera_start():
    """
    Start the real-time camera processing pipeline.

    ---
    tags:
      - Camera
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        required: false
        schema:
          type: object
          properties:
            source:
              type: string
              description: RTSP URL, webcam index, or video file path
            intersection_id:
              type: string
    responses:
      200:
        description: Camera pipeline started
      503:
        description: Vision dependencies not installed
    """
    global camera_pipeline

    with camera_pipeline_lock:
        if camera_pipeline is not None and camera_pipeline.get_status().get("running"):
            return APIResponse.error(
                "CAMERA_ALREADY_RUNNING",
                "Camera pipeline is already running"
            ), 400

        try:
            data = request.get_json() or {}
            pipeline = _build_camera_pipeline(
                source=data.get("source"),
                intersection_id=data.get("intersection_id"),
            )
            pipeline.start()
            camera_pipeline = pipeline
            logger.info(f"Camera pipeline started by {g.user['email']}")
            return APIResponse.success(
                data=pipeline.get_status(),
                message="Camera pipeline started"
            ), 200

        except RuntimeError as e:
            logger.error(f"Camera start failed (dependencies): {str(e)}")
            return APIResponse.error(
                "VISION_DEPENDENCIES_MISSING",
                str(e)
            ), 503
        except Exception as e:
            logger.exception(f"Camera start error: {str(e)}")
            return APIResponse.error(
                "CAMERA_START_FAILED",
                f"Failed to start camera pipeline: {str(e)}"
            ), 500


@app.route("/api/camera/stop", methods=["POST"])
@RoleManager.require_role("ADMIN", "TRAFFIC_OPERATOR")
def camera_stop():
    """
    Stop the camera processing pipeline.

    ---
    tags:
      - Camera
    security:
      - Bearer: []
    responses:
      200:
        description: Camera pipeline stopped
      400:
        description: Pipeline not running
    """
    global camera_pipeline

    with camera_pipeline_lock:
        if camera_pipeline is None:
            return APIResponse.error(
                "CAMERA_NOT_RUNNING",
                "Camera pipeline is not running"
            ), 400

        pipeline = camera_pipeline
        camera_pipeline = None

    pipeline.stop()
    logger.info(f"Camera pipeline stopped by {g.user['email']}")
    return APIResponse.success(message="Camera pipeline stopped"), 200


@app.route("/api/camera/status", methods=["GET"])
def camera_status():
    """
    Get camera pipeline status.

    ---
    tags:
      - Camera
    responses:
      200:
        description: Pipeline status
    """
    with camera_pipeline_lock:
        if camera_pipeline is None:
            return APIResponse.success(
                data={"running": False, "pipeline": None},
                message="Camera pipeline is not running"
            ), 200

        return APIResponse.success(
            data=camera_pipeline.get_status(),
            message="Camera pipeline status retrieved"
        ), 200


@app.route("/api/camera/frame", methods=["GET"])
def camera_frame():
    """
    Stream annotated camera frames as MJPEG.

    ---
    tags:
      - Camera
    responses:
      200:
        description: MJPEG stream
      400:
        description: Pipeline not running
    """
    with camera_pipeline_lock:
        pipeline = camera_pipeline
        running = pipeline is not None and pipeline.get_status().get("running")

    if not running:
        return APIResponse.error(
            "CAMERA_NOT_RUNNING",
            "Camera pipeline is not running"
        ), 400

    def generate():
        try:
            import cv2
        except ImportError:
            yield b""
            return

        while True:
            if not pipeline.get_status().get("running"):
                break
            frame = pipeline.get_annotated_frame()
            if frame is None:
                time.sleep(0.1)
                continue
            ok, jpeg = cv2.imencode(".jpg", frame)
            if not ok:
                time.sleep(0.1)
                continue
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + jpeg.tobytes()
                + b"\r\n"
            )
            time.sleep(0.1)

    return Response(
        generate(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


# ──────────────────────────────────────────────
# REALTIME (PHASE 2): WEBSOCKET SETUP
# ──────────────────────────────────────────────
socket_manager = SocketManager() if REALTIME_ENABLED else None
if socket_manager is not None:
    socket_manager.init_app(app)

data_stream = None
if socket_manager is not None and socket_manager.available:
    data_stream = DataStream(
        socket_manager,
        pipeline_provider=lambda: camera_pipeline,
    )


# ──────────────────────────────────────────────
# PHASE 4: INTELLIGENCE (ADVANCED)
# ──────────────────────────────────────────────
try:
    from services.intelligence_service import IntelligenceService
    from events import Event, EventType, EventBus
    intelligence_service = IntelligenceService()
    if not intelligence_service.available:
        intelligence_service = None
    else:
        logger.info("Phase 4 intelligence service ready")
except ImportError as e:
    logger.warning(f"Intelligence modules unavailable: {str(e)}")
    intelligence_service = None

# Phase 4 Step 4.5: commuter mobile app feed (public, read-only)
try:
    from services.mobile_service import MobileService
    mobile_service = MobileService(
        intelligence_service=intelligence_service,
        health_monitor=health_monitor,
    )
    logger.info("Phase 4 mobile service ready")
except ImportError as e:
    logger.warning(f"Mobile service unavailable: {str(e)}")
    mobile_service = None


def _publish_alert(alert):
    """Push an anomaly alert to WebSocket clients and the event bus."""
    if not alert:
        return
    try:
        if socket_manager is not None and socket_manager.available:
            socket_manager.emit_alert(alert)
        if EventBus:
            EventBus.publish(Event(EventType.ANOMALY_DETECTED, alert))
    except Exception as e:
        logger.debug(f"Alert publish failed: {str(e)}")
    # Phase 4 Step 4.5: forward alerts to the city TMC webhooks
    if intelligence_service is not None:
        try:
            intelligence_service.tmc.notify(alert)
        except Exception as e:
            logger.debug(f"TMC notification failed: {str(e)}")
    # Phase 4 Step 4.5: surface the alert as a public incident
    if mobile_service is not None:
        try:
            mobile_service.publish_alert(alert)
        except Exception as e:
            logger.debug(f"Mobile incident publish failed: {str(e)}")


def _on_pipeline_result(result):
    """
    Camera pipeline callback: forward counts/timings to WebSocket
    clients and run Phase 4 anomaly detection on each frame.
    """
    counts = (result or {}).get("counts") or {}
    try:
        if socket_manager is not None and socket_manager.available:
            socket_manager.emit_pipeline_result(result)
    except Exception as e:
        logger.debug(f"Pipeline result emit failed: {str(e)}")

    if intelligence_service is not None:
        for alert in intelligence_service.observe_counts(counts):
            _publish_alert(alert)

    # Phase 4 Step 4.5: keep the mobile snapshot fresh
    if mobile_service is not None:
        try:
            mobile_service.publish_snapshot(
                counts=counts,
                timings=(result or {}).get("timings") or {},
            )
        except Exception as e:
            logger.debug(f"Mobile snapshot publish failed: {str(e)}")


# ──────────────────────────────────────────────
# PHASE 4: INTELLIGENCE ROUTES
# ──────────────────────────────────────────────
@app.route("/api/anomaly/check", methods=["POST"])
@RoleManager.require_permission("predict")
def anomaly_check():
    """
    Check per-direction counts for traffic anomalies.

    ---
    tags:
      - Intelligence
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        required: false
        schema:
          type: object
          properties:
            counts:
              type: object
              description: north/south/east/west vehicle counts
    responses:
      200:
        description: Anomaly check complete
    """
    if intelligence_service is None:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE", "Intelligence service is not available"
        ), 503
    try:
        data = request.get_json() or {}
        result = intelligence_service.check_anomalies(data.get("counts"))
        for alert in result.get("alerts", []):
            _publish_alert(alert)
        return APIResponse.success(
            data=result, message="Anomaly check completed"
        ), 200
    except Exception as e:
        logger.exception(f"Anomaly check error: {str(e)}")
        return APIResponse.error(
            "ANOMALY_ERROR", f"Anomaly check failed: {str(e)}"
        ), 500


@app.route("/api/anomaly/status", methods=["GET"])
def anomaly_status():
    """
    Anomaly detector status (history size, recent alerts).

    ---
    tags:
      - Intelligence
    responses:
      200:
        description: Detector status
    """
    if intelligence_service is None:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE", "Intelligence service is not available"
        ), 503
    return APIResponse.success(
        data=intelligence_service.anomaly_status(),
        message="Anomaly detector status",
    ), 200


@app.route("/api/forecast", methods=["POST"])
@RoleManager.require_permission("predict")
def forecast():
    """
    Forecast next-step vehicle counts (feeds counts into history).

    ---
    tags:
      - Intelligence
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        required: false
        schema:
          type: object
          properties:
            steps:
              type: integer
            counts:
              type: object
    responses:
      200:
        description: Forecast
    """
    if intelligence_service is None:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE", "Intelligence service is not available"
        ), 503
    try:
        data = request.get_json() or {}
        steps = int(data.get("steps", 5))
        result = intelligence_service.forecast(
            steps=steps, counts=data.get("counts")
        )
        return APIResponse.success(
            data=result, message=f"Forecast for next {steps} steps"
        ), 200
    except Exception as e:
        logger.exception(f"Forecast error: {str(e)}")
        return APIResponse.error(
            "FORECAST_ERROR", f"Forecast failed: {str(e)}"
        ), 500


@app.route("/api/forecast/congestion", methods=["GET"])
def congestion_forecast():
    """
    Predicted congestion at 5/10/15 minute horizons.

    ---
    tags:
      - Intelligence
    responses:
      200:
        description: Congestion horizons
    """
    if intelligence_service is None:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE", "Intelligence service is not available"
        ), 503
    minutes = request.args.get("minutes", type=int)
    return APIResponse.success(
        data=intelligence_service.congestion_forecast(minutes),
        message="Congestion forecast generated",
    ), 200


@app.route("/api/intersections/optimize", methods=["POST"])
@RoleManager.require_permission("optimize")
def optimize_intersections():
    """
    Global PSO across multiple intersections (with green wave +
    emergency preemption support).

    ---
    tags:
      - Intelligence
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            demands:
              type: object
              description: per-intersection per-direction vehicle counts
            arterial:
              type: array
              items:
                type: string
            emergency:
              type: object
    responses:
      200:
        description: Optimized timings for all intersections
    """
    if intelligence_service is None:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE", "Intelligence service is not available"
        ), 503
    try:
        data = request.get_json()
        if not data or "demands" not in data:
            return APIResponse.error(
                "MISSING_FIELD", "demands is required"
            ), 422
        result = intelligence_service.optimize_intersections(
            demands=data["demands"],
            arterial=data.get("arterial"),
            emergency=data.get("emergency"),
        )
        logger.info(
            f"Multi-intersection optimization by {g.user['email']}: "
            f"{len(result['intersections'])} intersections "
            f"(fitness={result['global_fitness']})"
        )
        return APIResponse.success(
            data=result, message="Intersection coordination complete"
        ), 200
    except TrafficAPIError as error:
        response_data, status_code = handle_error(error)
        return response_data, status_code
    except Exception as e:
        logger.exception(f"Intersection optimization error: {str(e)}")
        return APIResponse.error(
            "COORDINATION_ERROR",
            f"Intersection optimization failed: {str(e)}",
        ), 500


@app.route("/api/controller/apply", methods=["POST"])
@RoleManager.require_permission("optimize")
def controller_apply():
    """
    Push signal timings to the traffic controller (fixed fallback
    when the controller is unreachable).

    ---
    tags:
      - Intelligence
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            intersection_id:
              type: string
            timings:
              type: object
            override:
              type: boolean
    responses:
      200:
        description: Timings applied
    """
    if intelligence_service is None:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE", "Intelligence service is not available"
        ), 503
    try:
        data = request.get_json() or {}
        result = intelligence_service.apply_controller_timings(
            intersection_id=data.get("intersection_id", ""),
            timings=data.get("timings"),
            override=bool(data.get("override", False)),
        )
        message = "Timings applied to controller"
        if result.get("fallback"):
            message = "Controller unreachable — fixed fallback timings applied"
        return APIResponse.success(data=result, message=message), 200
    except TrafficAPIError as error:
        response_data, status_code = handle_error(error)
        return response_data, status_code
    except Exception as e:
        logger.exception(f"Controller apply error: {str(e)}")
        return APIResponse.error(
            "CONTROLLER_ERROR", f"Failed to apply timings: {str(e)}"
        ), 500


@app.route("/api/controller/status", methods=["GET"])
def controller_status():
    """
    Controller client status (last apply, fallback state).

    ---
    tags:
      - Intelligence
    responses:
      200:
        description: Controller client status
    """
    if intelligence_service is None:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE", "Intelligence service is not available"
        ), 503
    return APIResponse.success(
        data=intelligence_service.controller_status(),
        message="Controller client status",
    ), 200


@app.route("/api/routes/suggest", methods=["POST"])
@RoleManager.require_permission("predict")
def routes_suggest():
    """
    Suggest alternative routes around congestion (Step 4.4).

    ---
    tags:
      - Intelligence
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            network:
              type: object
              description: Optional road network {intersections, roads};
                           a built-in default is used when omitted
            origin:
              type: string
            destination:
              type: string
            k:
              type: integer
            avoid:
              type: array
              items:
                type: string
    responses:
      200:
        description: Ranked alternative routes
    """
    if route_advisor is None:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE", "Route advisor is not available"
        ), 503
    try:
        data = request.get_json() or {}
        origin = data.get("origin")
        destination = data.get("destination")
        if not origin or not destination:
            return APIResponse.error(
                "MISSING_FIELD", "origin and destination are required"
            ), 422
        network = data.get("network")
        if network:
            route_advisor.load_network(network)
        else:
            route_advisor.load_network(_default_route_network())
        result = route_advisor.suggest_routes(
            origin, destination,
            k=int(data.get("k", 3)),
            avoid=data.get("avoid"),
        )
        return APIResponse.success(
            data=result, message="Route suggestions generated"
        ), 200
    except ValueError as e:
        return APIResponse.error("INVALID_NETWORK", str(e)), 422
    except TrafficAPIError as error:
        response_data, status_code = handle_error(error)
        return response_data, status_code
    except Exception as e:
        logger.exception(f"Route suggestion error: {str(e)}")
        return APIResponse.error(
            "ROUTE_ERROR", f"Route suggestion failed: {str(e)}"
        ), 500


@app.route("/api/routes/status", methods=["GET"])
def routes_status():
    """
    Route advisor network status (Step 4.4).

    ---
    tags:
      - Intelligence
    responses:
      200:
        description: Network stats
    """
    if route_advisor is None:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE", "Route advisor is not available"
        ), 503
    return APIResponse.success(
        data=route_advisor.get_status(),
        message="Route advisor status",
    ), 200


# Phase 4 Step 4.4: alternative-route advisor (road network seeded per request)
try:
    from intelligence.routing import RouteAdvisor
    route_advisor = RouteAdvisor()
    logger.info("Phase 4 route advisor ready")
except ImportError as e:
    logger.warning(f"Route advisor unavailable: {str(e)}")
    route_advisor = None

# Phase 5 Step 5.1: enterprise event bridge (logging + optional Kafka)
try:
    from workers.event_bridge import EventBridge
    event_bridge = EventBridge()
    event_bridge.start()
    logger.info("Phase 5 event bridge ready")
except ImportError as e:
    logger.warning(f"Event bridge unavailable: {str(e)}")
    event_bridge = None


def _default_route_network():
    """Default demo road network for /api/routes/suggest."""
    return {
        "intersections": {
            "INT_001": {"name": "Main & 1st", "congestion": "LOW"},
            "INT_002": {"name": "Main & 2nd", "congestion": "LOW"},
            "INT_003": {"name": "Main & 3rd", "congestion": "MEDIUM"},
            "INT_004": {"name": "Oak & 1st", "congestion": "LOW"},
            "INT_005": {"name": "Oak & 2nd", "congestion": "LOW"},
            "INT_006": {"name": "Oak & 3rd", "congestion": "LOW"},
        },
        "roads": [
            {"from": "INT_001", "to": "INT_002", "distance_km": 0.8, "name": "Main St (1st-2nd)"},
            {"from": "INT_002", "to": "INT_003", "distance_km": 0.8, "name": "Main St (2nd-3rd)"},
            {"from": "INT_001", "to": "INT_004", "distance_km": 0.6, "name": "1st St"},
            {"from": "INT_002", "to": "INT_005", "distance_km": 0.6, "name": "2nd St"},
            {"from": "INT_003", "to": "INT_006", "distance_km": 0.6, "name": "3rd St"},
            {"from": "INT_004", "to": "INT_005", "distance_km": 0.8, "name": "Oak Ave (1st-2nd)"},
            {"from": "INT_005", "to": "INT_006", "distance_km": 0.8, "name": "Oak Ave (2nd-3rd)"},
        ],
    }


# ──────────────────────────────────────────
# PHASE 4: MOBILE APP API (public, read-only)
# ──────────────────────────────────────────
@app.route("/api/mobile/status", methods=["GET"])
def mobile_status():
    """
    Real-time traffic status for the commuter mobile app.

    ---
    tags:
      - Mobile
    responses:
      200:
        description: Current counts, timings and congestion horizons
    """
    if mobile_service is None:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE", "Mobile service is not available"
        ), 503
    return APIResponse.success(
        data=mobile_service.get_traffic_status(),
        message="Mobile traffic status",
    ), 200


@app.route("/api/mobile/travel-time", methods=["GET"])
def mobile_travel_time():
    """
    Estimated travel time for commuters.

    ---
    tags:
      - Mobile
    parameters:
      - name: distance_km
        in: query
        type: number
        required: true
      - name: congestion
        in: query
        type: string
        enum: [LOW, MEDIUM, HIGH]
    responses:
      200:
        description: ETA estimate
    """
    if mobile_service is None:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE", "Mobile service is not available"
        ), 503
    distance_km = request.args.get("distance_km", type=float)
    if not distance_km or distance_km <= 0:
        return APIResponse.error(
            "MISSING_FIELD", "distance_km (positive number) is required"
        ), 422
    congestion = request.args.get("congestion")
    if not congestion and intelligence_service is not None:
        try:
            horizons = intelligence_service.congestion_forecast().get("horizons", {})
            if horizons:
                congestion = next(iter(horizons.values())).get("level")
        except Exception:
            congestion = None
    return APIResponse.success(
        data=mobile_service.estimate_travel_time(distance_km, congestion or "LOW"),
        message="Travel time estimate",
    ), 200


@app.route("/api/mobile/incidents", methods=["GET"])
def mobile_incidents():
    """
    Recent public incidents (anomaly alerts) for the mobile app.

    ---
    tags:
      - Mobile
    parameters:
      - name: limit
        in: query
        type: integer
        default: 20
    responses:
      200:
        description: Incident list
    """
    if mobile_service is None:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE", "Mobile service is not available"
        ), 503
    limit = request.args.get("limit", default=20, type=int)
    return APIResponse.success(
        data=mobile_service.get_incidents(limit),
        message="Recent incidents",
    ), 200


@app.route("/api/mobile/summary", methods=["GET"])
def mobile_summary():
    """
    One-call home-screen payload for the mobile app.

    ---
    tags:
      - Mobile
    responses:
      200:
        description: Traffic + incidents + system summary
    """
    if mobile_service is None:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE", "Mobile service is not available"
        ), 503
    return APIResponse.success(
        data=mobile_service.get_app_summary(),
        message="Mobile summary",
    ), 200


@app.route("/api/tmc/status", methods=["GET"])
def tmc_status():
    """
    City Traffic Management Center client status (data exchange,
    webhook configuration, last push/notifications).

    ---
    tags:
      - Intelligence
    responses:
      200:
        description: TMC client status
    """
    if intelligence_service is None:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE", "Intelligence service is not available"
        ), 503
    return APIResponse.success(
        data=intelligence_service.tmc_status(),
        message="TMC client status",
    ), 200


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
        return app.send_static_file("pso_traffic_dashboard_connected.html")
    except Exception:
        return "PSO Traffic Dashboard", 200


@app.route("/mobile", methods=["GET"])
def mobile_web():
    """Serve the commuter mobile web client (Phase 5 Step 5.5)."""
    try:
        return app.send_static_file("mobile.html")
    except Exception:
        return "PSO Traffic Mobile", 200


# ──────────────────────────────────────────────
# PHASE 5: EVENT BRIDGE + MODEL LIFECYCLE ROUTES
# ──────────────────────────────────────────────
@app.route("/api/events/status", methods=["GET"])
@RoleManager.require_role("ADMIN")
def events_status():
    """
    Event bridge diagnostics (backends, forwarded/failed counts).

    ---
    tags:
      - System
    security:
      - Bearer: []
    responses:
      200:
        description: Event bridge status
    """
    if event_bridge is None:
        return APIResponse.error(
            "SERVICE_UNAVAILABLE", "Event bridge is not available"
        ), 503
    return APIResponse.success(
        data=event_bridge.get_status(),
        message="Event bridge status",
    ), 200


@app.route("/api/models/retrain", methods=["POST"])
@RoleManager.require_permission("optimize")
def models_retrain():
    """
    Trigger a model retraining run (Phase 5 Step 5.4).

    Uses the Celery queue when a broker is reachable; otherwise runs
    the AutoML search synchronously. `quick=true` runs a lighter
    search.

    ---
    tags:
      - Intelligence
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        schema:
          type: object
          properties:
            quick:
              type: boolean
    responses:
      200:
        description: Retraining result or queued task id
    """
    data = request.get_json() or {}
    quick = bool(data.get("quick", False))
    g.user_email = g.user.get("email", "unknown") if hasattr(g, "user") else "unknown"
    logger.info(f"Model retrain requested by {g.user_email} (quick={quick})")

    # Prefer the background queue when Celery/Redis are available
    try:
        from workers.tasks.model_tasks import retrain_model_task
        async_result = retrain_model_task.apply_async(kwargs={"quick": quick})
        # Brief wait: if the broker is dead, apply_async still returns
        # an id, so probe for immediate failure.
        try:
            result = async_result.get(timeout=2)
            return APIResponse.success(
                data={"mode": "queued", "task_id": async_result.id,
                      "result": result},
                message="Retraining completed",
            ), 200
        except Exception:
            return APIResponse.success(
                data={"mode": "queued", "task_id": async_result.id},
                message="Retraining queued — check back shortly",
            ), 202
    except Exception as queue_error:
        logger.warning(f"Celery queue unavailable ({queue_error}) — running synchronously")

    try:
        from intelligence.automl import run_automl
        report = run_automl(quick=quick)
        return APIResponse.success(
            data={"mode": "synchronous", "best_model": report.get("best_model"),
                  "results": report.get("results")},
            message="Retraining completed",
        ), 200
    except Exception as e:
        logger.exception(f"Retraining failed: {str(e)}")
        return APIResponse.error(
            "RETRAIN_ERROR", f"Retraining failed: {str(e)}"
        ), 500


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

    # Phase 2: Start live data stream (WebSocket dashboard updates)
    if socket_manager is not None and socket_manager.available and data_stream is not None:
        data_stream.start()
        logger.info("✓ Live WebSocket data stream started")

    if socket_manager is not None and socket_manager.available:
        socket_manager.run(
            app,
            host=config.HOST,
            port=config.PORT,
            debug=config.DEBUG,
        )
    else:
        app.run(
            host=config.HOST,
            port=config.PORT,
            debug=config.DEBUG,
            use_reloader=config.DEBUG
        )
