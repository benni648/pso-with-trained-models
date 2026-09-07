# ======================================================================
# PSO SMART TRAFFIC SIGNAL OPTIMIZATION SYSTEM
# MASTER DEVELOPMENT PLAN & PROJECT DOCUMENTATION  (v7.0 — INDUSTRY READY)
# ======================================================================
# Version:   7.0
# Date:      2026-09-07
# Status:    Phases 0–5 BUILT & WORKING. Phase 6 = industry-readiness hardening.
#
# PHASE STATUS SNAPSHOT
#   Phase 0 — Foundation           ✅ BUILT     server starts, tests pass
#   Phase 1 — Vision pipeline      ✅ BUILT     (deps: ultralytics/opencv/torch)
#   Phase 2 — WebSocket dashboard  ✅ BUILT     (deps: flask-socketio/eventlet)
#   Phase 3 — Production infra     ✅ BUILT     Dockerfile/compose/nginx/gunicorn/metrics
#   Phase 4 — Advanced intelligence ✅ BUILT    anomaly/Holt/predict-congestion/multi-PSO/
#                                             controller/TMC/routing/AutoML/deep models/mobile API
#   Phase 5 — Scale & client       ✅ BUILT     event bridge/Grafana/NTCIP/retrain/mobile.html
#   Phase 6 — Industry readiness   🔲 TODO      security/auth/backend/ML/DB/deploy/obs/
#                                             frontend/tests/config/docs hardening
#
# HOW TO USE THIS DOC
#   - Every Phase section lists STATUS, WHAT EXISTS, and a TODO checklist.
#   - Every TODO item is tagged with one of 11 review areas:
#       [SEC] Security · [AUTH] Auth/RBAC · [BACK] Backend/architecture
#       [ML]  ML/prediction · [DB]  Database · [DEP] Deployment/ops
#       [OBS] Observability · [FE]  Frontend/client · [TST] Testing
#       [CFG] Configuration/env · [DOC] Documentation
#   - Priority is per-item: P0 (must fix before real deploy), P1 (strong),
#     P2 (polish). Work in priority order within a phase.
# ======================================================================


# ======================================================================
# 1. PROJECT OVERVIEW  (short)
# ======================================================================
# Real-time PSO + ML traffic signal optimization:
#   camera → YOLOv8 detect → track → per-direction zone count
#   → RF/LSTM/Transformer predictor → PSO optimize → signal timings
#   → controller (REST or NTCIP-1202 adapter) + live dashboard (WebSocket)
#   → TMC city integration + mobile commuter feed + event streaming.
#
# User roles (current, in-memory JWT): ADMIN, TRAFFIC_OPERATOR, VIEWER.
# Live server:  python api/app.py   (port 5000)
# Mobile client: http://localhost:5000/mobile   (public, read-only)
# ======================================================================


# ======================================================================
# 2. REVIEW AREAS — KEY (all 11 areas, no omissions)
# ======================================================================
# Every remaining item in this doc is tagged with one of:
#
#  [SEC]  Security — secrets, passwords, CORS, headers, rate limiting, /metrics auth
#  [AUTH] Authentication/RBAC — DB users vs in-memory auth, token revocation, user source
#  [BACK] Backend architecture — app.py size, globals, sys.path, init ordering, cohesion
#  [ML]   ML/prediction — model promotion, LSTM/Transformer wired-in, feature-label parity,
#         forecast cadence assumption, training reproducibility
#  [DB]   Database — alembic URL, seed users, integrity errors, current live DB state
#  [DEP]  Deployment/ops — gunicorn worker class, .dockerignore, healthcheck, compose secrets,
#         grafana datasource UID, nginx not in compose, CI/CD, hardening headers
#  [OBS]  Observability — JSON logging, LoggerManager init ordering, after_request hooks
#  [FE]   Frontend/client — dashboard as giant static file, XSS audit, PWA, API consumer docs
#  [TST]  Testing — heavy model runs in tests, app factory for test speed, skips when no model,
#         missing test for enterprise_routes bug
#  [CFG]  Configuration/env — env var startup validation, CORS empty-string default,
#         JWT access-token lifetime, config-vs-settings blur
#  [DOC]  Documentation — Swagger vs reality, quick-start freshness, api/app.py docstring
# ======================================================================


# ======================================================================
# 3. CURRENT STATE ASSESSMENT (short)
# ======================================================================
# What exists and works:
#   - Flask app boots on port 5000 with JWT auth, RBAC, Swagger /docs, /api/health,
#     /api/predict, /api/optimize, /api/predict-and-optimize, settings, reports,
#     camera pipeline endpoints, Phase 4 intelligence routes, Phase 5 wires.
#   - Packages present: api/, config/, database/, events/, intelligence/, services/,
#     utils/, workers/, realtime/, vision/, monitoring/, frontend/, tests/, saved_models/.
#   - Trained artifacts: rf_model.pkl, lr_model.pkl, lstm_model.pt, transformer_model.pt,
#     automl_best_model.pkl, automl_report.json, model_meta.json.
#   - Docker: Dockerfile, docker-compose.yml (app/db/redis/worker/beat/prometheus/grafana),
#     nginx.conf, gunicorn.conf.py, .env.example.
#
# What is NOT live right now:
#   - PostgreSQL is not running; the enterprise subtree (/api/enterprise/* and any
#     DB-backed auth/audit/analytics) will fail at runtime because every path opens
#     a DB session. Decide: run DB-connected, or keep the graceful-degradation posture.
#   - Redis is not running; cache and Celery broker are unavailable; Celery tasks run
#     synchronously as a fallback in the API.
#   - The running /api/health was fixed from a 50s Redis hang to a ~2s TCP probe —
#     confirm that fix is in the file before any container deploy.
# ======================================================================


# ======================================================================
# 4. WHAT EXISTS — CURRENT FILE MAP (short, current)
# ======================================================================
# pso with trained model/
#  ├── api/
#  │     app.py  (big — ~1900 lines: everything wired here)
#  │     enterprise_routes.py  (17 enterprise endpoints; has request.context.user bug)
#  ├── config/
#  │     config.py  (class-based config + env overrides), settings.json
#  ├── database/
#  │     database.py, models.py (7 ORM models), migrations/env.py, migrations/versions/001_initial.py
#  ├── events/
#  │     events.py (EventBus + EventType + event classes), __init__.py
#  ├── intelligence/
#  │     anomaly.py, forecaster.py, coordinator.py, controller.py, tmc.py,
#  │     routing.py, automl.py, deep_model.py, ntcip_adapter.py, __init__.py
#  ├── services/
#  │     prediction_service, optimization_service, report_service, settings_service,
#  │     storage_service, audit_service, analytics_service, cache_service, intelligence_service,
#  │     mobile_service, __init__.py
#  ├── utils/
#  │     logger.py, errors.py, response.py, auth.py (in-memory JWT + DEMO_USERS),
#  │     health.py (TCP probe fix), __init__.py
#  ├── workers/
#  │     celery_app.py, event_bridge.py, tasks/model_tasks.py, tasks/*, __init__.py
#  ├── realtime/
#  │     socket_manager.py, data_stream.py, __init__.py
#  ├── vision/
#  │     pipeline.py, detector.py, tracker.py, counter.py, config.py, stream.py, __init__.py
#  ├── monitoring/
#  │     metrics.py, __init__.py, prometheus.yml,
#  │     grafana/provisioning/{datasources,dashboards}/..., grafana/dashboards/pso_traffic.json
#  ├── frontend/
#  │     pso_traffic_dashboard_connected.html  (giant single static file),
#  │     mobile.html
#  ├── tests/
#  │     conftest.py, test_auth.py, test_endpoints.py, test_services.py,
#  │     test_vision.py, test_intelligence.py, test_phase4_final.py, test_phase5.py
#  ├── saved_models/
#  │     rf_model.pkl, lr_model.pkl, lstm_model.pt, transformer_model.pt,
#  │     automl_best_model.pkl, automl_report.json, model_meta.json
#  ├── documentation/
#  │     (README, QUICK_START, PHASE_2_*, PROJECT_COMPLETION, QUICK_REFERENCE, INDEX, ARCHITECTURE, …)
#  ├── predict_traffic.py, pso_integration.py, train_model.py,
#  │     pso_traffic_preprocessed.csv, requirements.txt, run.bat, run.sh,
#  │     Dockerfile, docker-compose.yml, nginx.conf, gunicorn.conf.py, .env.example, .dockerignore
# ======================================================================


# ======================================================================
# 5. PHASE 0 — FOUNDATION  ✅ BUILT
# ======================================================================
# Status: server starts; JWT auth + RBAC + Swagger + predict/optimize/settings/reports;
# utils/, services/, workers/, tests/, train_model.py, rf_model.pkl all exist.
#
# TODO (only cleanup; nothing blocking):
#   [BACK]  Replace module-level sys.path insert in api/app.py with a proper package layout
#           (pyproject.toml or PYTHONPATH from the project root). P2.
#   [DOC]   The Phase 0 step-by-step build instructions in this plan are now obsolete —
#           keep this plan's Phase 0 section as "built; see tests/ + requirements.txt".
#           P2.
# ======================================================================


# ======================================================================
# 6. PHASE 1 — REAL-TIME CAMERA PIPELINE  ✅ BUILT
# ======================================================================
# Status: vision/ package (stream, detector, tracker, counter, config, pipeline)
# + camera endpoints (/api/camera/start|stop|status|frame MJPEG)
# + PredictionService.predict_from_camera_counts().
# Deps: ultralytics, opencv-python, deep-sort-realtime, torch.
# Imports are lazy — app runs without deps and returns 503 with install text.
#
# TODO:
#   [SEC]   Dashboard HTML is served as static content; audit it for any innerHTML use
#           with API data (XSS surface). The mobile.html feed escapes HTML — good. P1.
#   [FE]    The dashboard is one giant self-contained .html (inline CSS/JS, ~19k+ lines).
#           Good as a demo; for a product UI, split into a build pipeline with hashed/cacheable
#           assets. P2.
#   [ML]    Camera cadence assumption: the forecaster treats 1 observation ≈ 1 minute for the
#           5/10/15-minute congestion horizons. Document this assumption in the endpoint doc /
#           Swagger and/or make it configurable. P2.
# ======================================================================


# ======================================================================
# 7. PHASE 2 — WEBSOCKET LIVE DASHBOARD  ✅ BUILT
# ======================================================================
# Status: realtime/ (socket_manager, data_stream), Socket.IO events
# (vehicle_count, signal_timing, health_update, alert, subscribe/unsubscribe/request_frame),
# DataStream publisher (camera or simulation). flask-socketio + eventlet in requirements.
#
# TODO:
#   [DEP]   Default gunicorn worker class is "sync" in gunicorn.conf.py. eventlet IS installed
#           (requirements.txt) and flask-socketio is installed, but with sync workers Socket.IO
#           falls back to long-polling (works, less efficient) — real WebSockets need
#           GUNICORN_WORKER_CLASS=eventlet (or --worker-class eventlet). Decide and document the
#           intended worker class; set it in the compose CMD/env if WebSockets are required. P1.
#   [OBS]   Two @app.after_request hooks exist (one for duration logging, one for Prometheus
#           request counting). They stack fine, but note it. P2.
#   [DOC]   Confirm the live Swagger /docs includes all Phase 4/5 endpoints
#           (mobile, events/status, models/retrain, controller/tmc/routes, etc.). P2.
# ======================================================================


# ======================================================================
# 8. PHASE 3 — PRODUCTION INFRASTRUCTURE  ✅ BUILT
# ======================================================================
# Status: Dockerfile, docker-compose.yml (app/db/redis/worker/beat/prometheus/grafana),
# .dockerignore, .env.example, nginx.conf (MJPEG + Socket.IO proxy), gunicorn.conf.py,
# monitoring/metrics.py (/metrics with request counter + prediction/optimization latency
# histograms + model accuracy gauge + active connections gauge). prometheus-client in reqs.
#
# TODO:
#   [DEP]   .dockerignore — verify it excludes venv/, __pycache__/, *.pyc, .pytest_cache,
#           reports/, logs/, .git, etc. Otherwise the image is bloated and may carry local
#           artifacts. P1.
#   [DEP]   Healthcheck in Dockerfile calls GET /api/health — confirm the utils/health.py TCP
#           probe fix is present (was 50s hang due to redis-py IPv6/retry behavior). P0.
#   [DEP]   nginx.conf exists but there is NO nginx service in docker-compose.yml. Either add an
#           nginx service to compose, or remove nginx from the deploy story. P1.
#   [DEP]   Grafana admin password in compose is "admin" (GF_SECURITY_ADMIN_PASSWORD: admin).
#           Change it (via .env / gitignored env file). P1.
#   [DEP]   Prometheus has no built-in auth — protect it via nginx basic auth / network
#           restrictions if exposed beyond the internal compose network. P1.
#   [DEP]   grafana/dashboards/pso_traffic.json uses datasource UID "${DS_PROMETHEUS}" on every
#           panel. Ensure the provisioned Prometheus datasource actually has that UID, or the
#           panels render "no data source". Align UID in the datasource provisioning YAML with
#           the dashboard reference. P0 (dashboard will be empty otherwise).
#   [DEP]   docker-compose.yml hardcodes postgres/redis passwords (pso_user/pso_password) and
#           JWT_SECRET_KEY defaults to "change-me-in-production-64-char-min" via ${JWT_SECRET_KEY:-…}.
#           Use a gitignored .env file with real secrets; treat the compose defaults as placeholders
#           and document that. P1.
#   [SEC]   /metrics endpoint has no auth in Flask — every request counter/latency/accuracy metric
#           is publicly scrapeable. Protect it at nginx or add Flask-side auth if exposed. P1.
#   [SEC]   Hardening headers (CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy,
#           Permissions-Policy) are absent. Add at nginx/gunicorn or Flask middleware, especially
#           for the dashboard and mobile.html. P1.
#   [SEC]   CORS_ORIGINS default is "*" in DevelopmentConfig and compose defaults to "*". With
#           supports_credentials=True, wildcard origin is invalid per spec. Lock to real domains in
#           production. P1.
#   [CFG]   ProductionConfig.CORS_ORIGINS falls back to "".split(",") → [""], which may not be the
#           intended "no CORS" behavior. Verify intent. P2.
#   [DEP]   Dockerfile CMD is gunicorn -c gunicorn.conf.py api.app:app. If the app factory approach
#           is adopted (see Phase 6 Backend), adjust the CMD accordingly. P2.
#   [DEP]   No CI pipeline (lint, typecheck, test, build) exists. For industry readiness add one
#           (GitHub Actions or equivalent). P1.
#   [DOC]   Refresh quick-start docs (README, QUICK_START, PHASE_2_* docs) to match the current
#           compose stack (prometheus, grafana, beat, event bridge, mobile client). P2.
# ======================================================================


# ======================================================================
# 9. PHASE 5 — SCALE, INTEGRATION & CLIENT EXPERIENCE  ✅ BUILT
# ======================================================================
# Status: event bridge (LoggingBackend always-on + optional KafkaBackend via kafka-python +
# KAFKA_ENABLED), Grafana provisioning + compose monitoring stack, NTCIP-1202 adapter
# (CONTROLLER_PROTOCOL=ntcip), Celery beat nightly retrain + on-demand POST /api/models/retrain,
# mobile.html served at GET /mobile.
#
# TODO:
#   [AUTH]  /api/models/retrain requires "optimize" permission. Confirm that is the right gate
#           (it triggers ML retraining) and that the permission name is consistent with the role
#           matrix. P2.
#   [BACK]  EventBridge is created and start() is called at module level in api/app.py (outside an
#           app factory). It subscribes to the global EventBus at import time — fine for gunicorn
#           preload, but consider initializing it inside app setup so it doesn't start when the
#           module is imported in a REPL/test without an app. P2.
#   [OBS]   EventBridge's LoggingBackend emits one structured JSON line per event — good; consider
#           extending this pattern to per-request JSON logging for log aggregation (ELK/Datadog).
#           P2.
#   [FE]    mobile.html is served and consumes /api/mobile/* (status, travel-time, incidents,
#           summary). Good. If "mobile app" ambition grows, add PWA manifest + service worker.
#           P2.
#   [DOC]   Document the new Phase 5 endpoints in Swagger and in this plan's API reference.
#           P2.
# ======================================================================


# ======================================================================
# 10. PHASE 4 — ADVANCED INTELLIGENCE  ✅ BUILT
# ======================================================================
# Status: intelligence/ (anomaly, forecaster, coordinator, controller, tmc, routing, automl,
# deep_model, ntcip_adapter) + intelligence_service + mobile_service + routes:
#   /api/anomaly/check|status, /api/forecast, /api/forecast/congestion,
#   /api/intersections/optimize, /api/controller/apply|status, /api/tmc/status,
#   /api/routes/suggest|status, /api/mobile/status|travel-time|incidents|summary.
# Alerts flow: camera frame → detector + forecaster → WebSocket + EventBus + TMC webhooks +
# mobile incident feed.
# Deep models trained: lstm_model.pt (avg MAE 0.458), transformer_model.pt (avg MAE 0.478),
# automl_best_model.pkl (Ridge R²=0.9573). Production API still serves rf_model.pkl (MAE ~0.28).
#
# TODO:
#   [ML]    AutoML winner (automl_best_model.pkl) is computed but NOT wired into the live predictor —
#           the API still loads rf_model.pkl. Either automate promotion (retrain → validate → swap
#           the active model file or update a config pointer / symlink) or clearly label AutoML as an
#           offline report tool. P1.
#   [ML]    LSTM (lstm_model.pt) and Transformer (transformer_model.pt) are trained but not served —
#           no inference path loads them. Add a model-selection mechanism (env/config → active model)
#           or remove the claim that they are "available" in the running system. P1.
#   [ML]    Feature/label parity: predict_traffic.py and automl.py assume congestion_level_enc is
#           pre-computed in the CSV, while PredictionService.predict_from_camera_counts recomputes
#           congestion from total volume (>=30 HIGH, >=15 MEDIUM). Verify the training CSV's encoding
#           used the SAME thresholds; if not, the model is trained on different labels than it sees in
#           production. P1.
#   [ML]    Training reproducibility: multiple artifacts exist (rf, lr, lstm, transformer, automl
#           winner) with no single manifest of which script+params produced each. Add a training
#           manifest / Makefile / justfile that records provenance. P2.
#   [ML]    model_meta.json has recommended_model: "rf_model.pkl" but no startup validation that the
#           pointed file matches (no hash/version check). Add a hash check on boot to catch mismatched
#           model/meta pairs. P2.
#   [ML]    forecast / predict_congestion extrapolates step forecasts assuming 1 observation/minute for
#           the 5/10/15 min horizons (see also Phase 1 [ML] cadence point). Document + optionally
#           configure. P2.
# ======================================================================


# ======================================================================
# 11. PHASE 6 — INDUSTRY READINESS HARDENING  🔲 TODO  (organized by area)
#     This is the cross-cutting work that turns "it runs" into "it is deployable".
#     Nothing here is done yet. Priority order: P0 → P1 → P2.
# ======================================================================

## 11.1  [SEC]  SECURITY  — P0/P1
#   P0 • Replace all default secrets before any real deploy:
#        - SECRET_KEY, JWT_SECRET_KEY, JWT_SECRET in .env.example / compose / Dockerfile.
#        - Add a startup guard in ProductionConfig that REFUSES to boot (or at least loudly logs
#          and warns) when these are still the default values. Implement as validate_environment()
#          that runs once at startup. (config.py / app.py)
#   P0 • Add password hashing if you move to DB-backed users: bcrypt or argon2. Cannot store
#        plaintext passwords in users.hashed_password column meaningfully. (utils/auth.py + DB user
#        flow)  — see 11.2.
#   P1 • Implement the rate limiter that the config promises: RATE_LIMIT_ENABLED /
#        RATE_LIMIT_REQUESTS / RATE_LIMIT_PERIOD exist in config.py but no middleware enforces them.
#        Add a real limiter (flask-limiter or custom) on the API, especially /login and /api/*. P1.
#   P1 • Add security hardening headers (CSP, X-Content-Type-Options, X-Frame-Options,
#        Referrer-Policy, Permissions-Policy) at nginx or Flask. P1.
#   P1 • Lock CORS to real domains in production; remove wildcard origin with credentials. P1.
#   P1 • Protect /metrics (Flask-side auth or nginx). P1.
#   P2 • Consolidate SECRET_KEY vs JWT_SECRET_KEY — two env vars for essentially the same concern;
#        document why both exist or unify. P2.

## 11.2  [AUTH]  AUTHENTICATION / RBAC  — P0/P1
#   P0 • Fix the in-memory vs DB user split. Today:
#        - utils/auth.py authenticates only DEMO_USERS (in-memory, plaintext passwords).
#        - database/models.py has a full User ORM with hashed_password, is_active, is_admin, etc.
#        - Login in app.py calls AuthManager.login() which only knows DEMO_USERS.
#        - The DB users table exists but is NEVER used for login or permission checks.
#        Decide which is authoritative:
#          (a) Stay demo/in-memory for now and remove/refactor the unused DB user schema from the
#              "auth" story, OR
#          (b) Build a real DB-backed auth path: add bcrypt hashing, a user seed script that creates
#              the default admin/operator/viewer in PostgreSQL, and make AuthManager.login query the DB.
#        This is the single biggest auth integrity issue. P0.
#   P0 • Fix enterprise_routes.py: it references request.context.user (line that does audit logging)
#        but the auth decorators set g.user. This will raise AttributeError at runtime on any
#        enterprise endpoint that writes audit logs. Change to g.user. P0.
#   P1 • Token revocation is in-memory (_revoked_tokens = set()) — lost on restart and not shared
#        across gunicorn workers. For a real app: Redis-backed token blocklist OR short-lived access
#        tokens with refresh-token rotation persisted in DB. P1.
#   P1 • Standardize the "current user" path: a single @authenticate decorator that sets g.user +
#        g.auth_context, then role/permission decorators just inspect it (today both decorators decode
#        the token and set g.user, duplicating work). P2.
#   P2 • Permission-to-role map is static in config.py (ROLES dict) — adding permissions requires code
#        change + redeploy. For extensibility, make it DB- or config-file-driven, or at least document
#        that it is fixed. P2.

## 11.3  [BACK]  BACKEND ARCHITECTURE  — P1
#   P1 • api/app.py is ~1900+ lines and does everything: config, service init, middleware, auth
#        routes, ops routes, health, settings, reports, camera lifecycle, WebSocket setup, Phase 4
#        intelligence wiring, Phase 5 event bridge + mobile + TMC + route advisor + two callbacks
#        (_publish_alert, _on_pipeline_result) + ~15 endpoint handlers.
#        Refactor into:
#          - create_app(config_override) factory
#          - blueprints: auth_bp, ops_bp (predict/optimize/settings/reports),
#            camera_bp, intelligence_bp (anomaly/forecast/intersections/controller/routes/tmc),
#            mobile_bp, enterprise_bp, events_bp, models_bp
#          - a separate service-wiring module (build_intelligence_service, build_mobile_service,
#            build_event_bridge, build_socket_manager, build_data_stream)
#        This is the biggest maintainability win. P1.
#   P1 • Global mutable singletons in app.py (camera_pipeline, socket_manager, data_stream,
#        intelligence_service, mobile_service, route_advisor, event_bridge) are per-worker after fork,
#        which is acceptable, but document the worker-singularity assumption explicitly. P2.
#   P2 • The event bridge / some optional-service try/except import patterns are duplicated ~6 times
#        with slightly different logging. A small import_optional("module", "warning msg") helper would
#        clean this up. P2.
#   P2 • Verify services/intelligence_service.py __init__ fully assigns self.available in all paths
#        (the NTCIP block looked possibly incomplete in one read window — confirm). P2.

## 11.4  [ML]  ML / PREDICTION  — P1/P2   (also see Phase 4 section)
#   (See Phase 4 TODO list — it overlaps this area. Summary of cross-references:)
#   P1 • Wire AutoML/deep-model selection into the live predictor or clearly mark them offline-only.
#   P1 • Verify training vs inference congestion encoding parity.
#   P2 • Add model provenance manifest; add startup model/meta hash check.

## 11.5  [DB]  DATABASE  — P0/P1
#   P0 • Decide DB-live vs graceful-degradation posture (see Current State). If you want enterprise
#        routes + DB auth + audit + analytics to actually work, run PostgreSQL in compose and set
#        DATABASE_URL. Today the app degrades silently, which is resilient but means the enterprise
#        subtree is effectively dead in the current run. Document the choice. P0.
#   P1 • Alembic env.py hardcodes a DB URL fallback to localhost postgres when sqlalchemy.url isn't in
#        the alembic config — make it read DATABASE_URL from the environment explicitly, or generate
#        alembic.ini from .env. P1.
#   P1 • Migration 001_initial.py and models.py don't align with the in-memory auth — if you go
#        DB-backed auth (11.2), add a seed script to create default users with hashed passwords. P1.
#   P2 • get_db() runs SELECT 1 inside a transaction just to ping; a raw engine ping is lighter. P2.
#   P2 • Add a dedicated handler for DB IntegrityError / duplicate-key → 409 instead of generic 500. P2.

## 11.6  [DEP]  DEPLOYMENT / OPS  — P0/P1   (also see Phase 3 section)
#   (See Phase 3 TODO list — overlaps. Key additional items:)
#   P0 • Confirm utils/health.py fix is in the file (50s → ~2s). P0.
#   P1 • .dockerignore verification; nginx-in-compose decision; grafana datasource UID alignment;
#        compose secrets + JWT default; Grafana admin password; Prometheus auth; eventlet worker class
#        for WebSockets; CI pipeline. (all listed in Phase 3 TODO — carry them here as the cross-phase
#        deployment checklist.)
#   P2 • Dockerfile CMD uses "api.app:app" — if you adopt the app factory, update the CMD and
#        gunicorn.conf.py entrypoint. P2.

## 11.7  [OBS]  OBSERVABILITY  — P2
#   P2 • Add per-request JSON logging (request_id, user_id, endpoint, status, duration) for log
#        aggregation (ELK/Datadog). Today logs are plain text; the event bridge already emits JSON lines
#        for events — extend the pattern. P2.
#   P2 • LoggerManager._setup() clears root handlers on first init — if a library or test imports a
#        logger before the app, it could init with defaults and the app config is ignored. Mostly OK
#        (app imports first), but fragile; note it. P2.
#   P2 • g.user['email'] is interpolated into some log lines (e.g. settings update) — safe inside
#        request context; be careful not to use that pattern outside a request. P2.

## 11.8  [FE]  FRONTEND / CLIENT  — P2
#   P2 • Audit dashboard HTML for XSS: any innerHTML/insertAdjacentHTML with API data must escape or
#        use text nodes. mobile.html already escapes incident messages — good; extend the same scrutiny
#        to the dashboard. P2.
#   P2 • Dashboard is one giant static file — split into a build pipeline with hashed/cacheable assets
#        if this is a product UI (not just a demo). P2.
#   P2 • Mobile "app" is currently a responsive page, not a PWA — if mobile app is a real goal, add
#        manifest.json + service worker for launchable/offline behavior. P2.
#   P2 • Publish a small API consumer guide / typed contract page in addition to Swagger, so external/
#        mobile consumers don't have to read the dashboard JS. P2.

## 11.9  [TST]  TESTING  — P1/P2
#   P1 • Heavy model runs (AutoML, deep-model) are in some tests — for CI, stub or skip them and keep
#        a separate "full training" job. Confirm the current test split doesn't do real training in CI.
#        P1.
#   P1 • conftest.py imports "from api.app import app" at module level, which boots the full app with
#        all optional-service try/except blocks — this is why the suite is slow. Refactor to a
#        create_app(config_override) factory and use it in conftest for speed + isolation. P1.
#   P2 • Many tests pytest.skip when models aren't available — ensure CI either carries the model
#        artifacts or treats skips as warnings, so a fresh clone doesn't silently pass a subset. P2.
#   P2 • Add a test that surfaces the enterprise_routes request.context.user bug (or fix it first and
#        add a regression test). P2.
#   P2 • Add tests for any new Phase 6 endpoints/helpers you introduce (rate limiter, env validation,
#        app factory, etc.). P2.

## 11.10  [CFG]  CONFIGURATION / ENVIRONMENT  — P1/P2
#   P1 • Add a startup validate_environment() that fails fast (or loudly warns in production) when
#        required secrets are still default/empty: SECRET_KEY, JWT_SECRET_KEY, DATABASE_URL when DB is
#        expected, etc. Run it once at boot in ProductionConfig / app startup. P1.
#   P1 • JWT access-token lifetime default is 24 hours (JWT_TOKEN_HOURS=24). For an operator tool on
#        the open internet, consider shorter access tokens + refresh rotation; for internal use 24h may
#        be acceptable — document the threat model. P1.
#   P2 • Clarify config.py ("env-driven settings") vs settings.json ("API-editable settings") — document
#        which settings are env-driven vs. runtime-editable. P2.
#   P2 • ProductionConfig CORS_ORIGINS "".split(",") → [""] edge case — verify intent or make it
#        produce an empty list. P2.

## 11.11  [DOC]  DOCUMENTATION  — P2
#   P2 • This MASTER_DEVELOPMENT_PLAN.md — keep it current (this v7.0 rewrite does that). P2.
#   P2 • Swagger /docs must match the actual live API surface (all Phase 4/5 endpoints). Verify and
#        refresh the docstrings / flasgger specs if they drift. P2.
#   P2 • Refresh README / QUICK_START / PHASE_2_* docs to reflect the current stack (compose monitoring,
#        event bridge, mobile client, NTCIP, retrain endpoint). P2.
#   P2 • api/app.py top docstring lists a subset of endpoints — update it to mention mobile, events,
#        models/retrain, controller/tmc/routes, etc., or move the endpoint catalog to Swagger only. P2.

# ======================================================================
# 12. API REFERENCE (short — current endpoints)
# ======================================================================
# Auth:
#   POST   /login           JWT login (DEMO_USERS today)
#   POST   /logout          revoke token (in-memory)
#   POST   /refresh         refresh access token
#
# Core ops:
#   POST   /api/predict                      prediction (RF)     [predict]
#   POST   /api/optimize                     PSO signal timings  [optimize]
#   POST   /api/predict-and-optimize         both in one call    [optimize]
#
# Info/settings/reports:
#   GET    /api/health
#   GET    /api/settings
#   POST   /api/settings                     admin-only
#   POST   /api/generate-report              admin/operator
#   GET    /api/reports
#
# Camera (Phase 1):
#   POST   /api/camera/start
#   POST   /api/camera/stop
#   GET    /api/camera/status
#   GET    /api/camera/frame                 MJPEG stream
#
# Phase 4 intelligence:
#   POST   /api/anomaly/check                [predict]
#   GET    /api/anomaly/status
#   POST   /api/forecast                     feed counts + forecast [predict]
#   GET    /api/forecast/congestion          5/10/15-min horizons
#   POST   /api/intersections/optimize       multi-intersection PSO [optimize]
#   POST   /api/controller/apply             push timings (REST/NTCIP) [optimize]
#   GET    /api/controller/status
#   GET    /api/tmc/status
#   POST   /api/routes/suggest               k alternative routes  [predict]
#   GET    /api/routes/status
#
# Phase 4.5 mobile (public, read-only):
#   GET    /api/mobile/status
#   GET    /api/mobile/travel-time           ?distance_km=&congestion=
#   GET    /api/mobile/incidents             ?limit=
#   GET    /api/mobile/summary
#
# Phase 5:
#   GET    /api/events/status                admin-only (event bridge diagnostics)
#   POST   /api/models/retrain               optimize permission; Celery or sync fallback
#   GET    /mobile                           mobile.html
#   GET    /metrics                         Prometheus (no auth today)
#   GET    /docs /docs/json                  Swagger/OpenAPI
#
# Enterprise (DB-backed, currently non-functional without PostgreSQL):
#   /api/enterprise/*  (datasets, predictions/history+stats, optimizations/history+best,
#                       analytics/overview+performance+trends, audit, models/register+activate,
#                       export/predictions, metrics, system-status)
# ======================================================================


# ======================================================================
# 13. DATABASE SCHEMA  (current — 7 ORM models)
# ======================================================================
#   users, traffic_data, predictions, optimizations, reports, audit_logs, model_registry
# See database/models.py + migrations/versions/001_initial.py.
# NOTE: this schema exists but is not used by the in-memory auth (see 11.2).
# ======================================================================


# ======================================================================
# 14. CONFIGURATION GUIDE  (short)
# ======================================================================
# Environment-driven (config.py class-based, env overrides):
#   ENVIRONMENT, DEBUG, HOST, PORT, SECRET_KEY, DATABASE_URL, REDIS_URL,
#   JWT_SECRET_KEY, JWT_TOKEN_HOURS, JWT_REFRESH_TOKEN_DAYS, CORS_ORIGINS,
#   LOG_LEVEL, PSO_N_PARTICLES/ITERATIONS/BOUNDS*, RATE_LIMIT_*, CACHE_*,
#   CONTROLLER_URL, TMC_URL, TMC_API_KEY, TMC_WEBHOOK_URLS, CONTROLLER_PROTOCOL,
#   KAFKA_ENABLED, KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC, CELERY_BROKER_URL,
#   CELERY_RESULT_BACKEND, GUNICORN_WORKER_CLASS, GUNICORN_WORKERS, GUNICORN_THREADS
#
# Runtime-editable (config/settings.json, API-editable via /api/settings):
#   simulation_speed, pso_iterations, pso_particles, model_selection,
#   logging_level, enable_notifications, enable_animations
#
# .env example: .env.example (copy to .env; .env must be gitignored).
# ======================================================================


# ======================================================================
# 15. DEPLOYMENT GUIDE  (short)
# ======================================================================
# Docker:
#   docker compose up --build
#   services: app, db, redis, worker, beat, prometheus, grafana
#   ports: 5000 (app), 5432 (db), 6379 (redis), 9090 (prometheus), 3000 (grafana admin/admin)
#   volumes: saved_models, reports, logs, pgdata, redisdata, promdata, grafanadata, grafana provisioning
#
# Bare metal:
#   gunicorn -c gunicorn.conf.py api.app:app
#   (for WebSockets: add -k eventlet when flask-socketio + eventlet installed)
#   nginx in front (nginx.conf) for TLS, CORS hardening, rate limiting, MJPEG + Socket.IO proxy
#
# Key deploy checks (see Phase 3/6 TODO):
#   - secrets replaced (SECRET_KEY, JWT_SECRET_KEY, compose passwords, grafana admin)
#   - .dockerignore excludes venv/pycache/reports/logs/.git
#   - healthcheck uses the fixed health.py (no 50s hang)
#   - grafana datasource UID matches dashboard ${DS_PROMETHEUS}
#   - nginx either in compose or removed from the story
#   - /metrics protected if exposed
#   - CORS locked to real domain
#   - (optional) eventlet worker class for real WebSockets
# ======================================================================


# ======================================================================
# 16. FILE STRUCTURE REFERENCE  (current — see section 4)
# ======================================================================
# (kept in sync with section 4 above.)
# ======================================================================


# ======================================================================
# END — MASTER DEVELOPMENT PLAN v7.0
# Next action: pick a phase/section and start executing, in P0→P1→P2 order.
# ======================================================================
