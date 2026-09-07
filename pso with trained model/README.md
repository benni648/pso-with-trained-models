# PSO Smart Traffic Signal Optimization — Professional Edition

A production-ready intelligent traffic signal optimization system with JWT authentication, role-based access control, comprehensive API documentation, and real-time monitoring.

## ✨ Key Features

### 🚦 Traffic Management
- **ML-Based Prediction**: Random Forest traffic forecasting with 95%+ R² accuracy
- **PSO Optimization**: Particle Swarm Optimization for signal timing
- **Per-Direction Analysis**: North, South, East, West vehicle predictions
- **Multi-Level Congestion**: LOW, MEDIUM, HIGH traffic state handling

### 🔐 Security & Access
- **JWT Authentication**: Secure token-based authentication
- **Role-Based Access**: Three-tier system (Admin, Operator, Viewer)
- **Permission Management**: Granular endpoint-level access control
- **Activity Logging**: Complete request/response audit trail

### 📊 Administration & Monitoring
- **Settings Management**: Real-time system parameter adjustment
- **Health Monitoring**: CPU, memory, uptime, and service status
- **Report Generation**: JSON, CSV, PDF traffic analysis reports
- **Detailed Logging**: Comprehensive application logging with rotation

### 📚 Developer Experience
- **Interactive API Docs**: Swagger UI at `/docs`
- **OpenAPI Spec**: Full API specification for integration
- **Example Requests**: Pre-built request templates
- **Comprehensive Testing**: 30+ test cases with pytest

## 📁 Project Structure

```
pso-traffic-system/
├── api/                       # Flask application
│   └── app.py                 # Main Flask app with all routes
│
├── services/                  # Business logic layer
│   ├── prediction_service.py  # ML prediction wrapper
│   ├── optimization_service.py # PSO optimization wrapper
│   ├── report_service.py      # Report generation
│   └── settings_service.py    # Settings management
│
├── config/                    # Configuration management
│   ├── config.py             # Centralized configuration
│   ├── settings.json         # Runtime settings (auto-generated)
│   └── __init__.py
│
├── utils/                     # Utilities
│   ├── logger.py             # Advanced logging system
│   ├── errors.py             # Custom exceptions
│   ├── response.py           # Standardized API responses
│   ├── auth.py               # JWT and RBAC
│   ├── health.py             # System health monitoring
│   └── __init__.py
│
├── frontend/                  # Web dashboard
│   └── pso_traffic_dashboard_connected.html
│
├── logs/                      # Application logs (auto-generated)
│   └── app.log
│
├── reports/                   # Generated reports (auto-generated)
│
├── tests/                     # Comprehensive test suite
│   ├── conftest.py           # Pytest configuration
│   ├── test_auth.py          # Authentication tests
│   ├── test_endpoints.py     # Endpoint tests
│   ├── test_services.py      # Service tests
│   └── __init__.py
│
├── documentation/            # Additional docs (auto-generated)
│
├── saved_models/             # ML models
│   ├── rf_model.pkl         # Random Forest model
│   ├── lr_model.pkl         # Linear Regression model
│   └── model_meta.json      # Model metadata
│
├── predict_traffic.py        # Legacy prediction module (preserved)
├── pso_integration.py        # Legacy PSO module (preserved)
├── train_model.py            # Model training script
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip

### Installation Steps

1. **Clone/Extract Project**
   ```bash
   cd "pso with trained model"
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   source venv/Scripts/activate  # Windows
   source venv/bin/activate      # Linux/Mac
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Verify Model Exists**
   ```bash
   ls saved_models/rf_model.pkl
   ```

5. **Start Server**
   ```bash
   python api/app.py
   ```

6. **Access Application**
   - Dashboard: http://localhost:5000
   - API Docs: http://localhost:5000/docs

---

## 🔐 Authentication & Login

### Default Credentials

| Email | Password | Role |
|-------|----------|------|
| admin@pso.com | admin123 | ADMIN |
| operator@pso.com | operator123 | TRAFFIC_OPERATOR |
| viewer@pso.com | viewer123 | VIEWER |

### Login via API
```bash
curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@pso.com","password":"admin123"}'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "user": {"email": "admin@pso.com", "role": "ADMIN"}
  }
}
```

### Use Token in Requests
```bash
curl -X POST http://localhost:5000/api/predict \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

---

## 👥 User Roles & Permissions

| Feature | Admin | Operator | Viewer |
|---------|-------|----------|--------|
| Predict Traffic | ✅ | ✅ | ✅ |
| Optimize Signals | ✅ | ✅ | ❌ |
| Generate Reports | ✅ | ✅ | ❌ |
| Manage Settings | ✅ | ❌ | ❌ |
| View Logs | ✅ | ❌ | ❌ |
| Manage Users | ✅ | ❌ | ❌ |

---

## 📡 API Endpoints

### Authentication Endpoints

**POST /login**
- Authenticate and get JWT token
- Body: `{"email": "...", "password": "..."}`

**POST /logout**
- Invalidate current token
- Requires: Bearer token

**POST /refresh**
- Get new access token from refresh token
- Body: `{"refresh_token": "..."}`

### Traffic Operations

**POST /api/predict**
- Predict next traffic state
- Requires: Bearer token, "predict" permission
- Body:
  ```json
  {
    "time_step": 45,
    "hour": 8,
    "density": 0.72,
    "avg_wait_time": 38.5,
    "congestion_level": "HIGH"
  }
  ```

**POST /api/optimize**
- Optimize signal timings
- Requires: Bearer token, "optimize" permission
- Body:
  ```json
  {
    "north_vehicles": 4.55,
    "south_vehicles": 4.35,
    "east_vehicles": 4.31,
    "west_vehicles": 4.34
  }
  ```

**POST /api/predict-and-optimize**
- Combined prediction and optimization
- Requires: Bearer token, "optimize" permission

### System Information

**GET /api/health**
- Server health status
- No authentication required
- Returns: Status, uptime, memory, CPU, model info

**GET /api/settings**
- Get current settings
- No authentication required

**POST /api/settings**
- Update settings
- Requires: Bearer token, "ADMIN" role

### Reporting

**POST /api/generate-report**
- Generate traffic report
- Requires: Bearer token, ADMIN or TRAFFIC_OPERATOR role
- Body:
  ```json
  {
    "title": "Weekly Traffic Report",
    "format": "json"
  }
  ```

**GET /api/reports**
- List recent reports
- Requires: Bearer token, ADMIN or TRAFFIC_OPERATOR role

### Documentation

**GET /docs**
- Interactive Swagger API documentation
- Full endpoint documentation with examples

---

## 📊 API Response Format

### Success Response
```json
{
  "success": true,
  "timestamp": "2024-01-15T10:30:45.123456",
  "message": "Operation successful",
  "data": {
    "north_vehicles": 4.55,
    "south_vehicles": 4.35,
    "east_vehicles": 4.31,
    "west_vehicles": 4.34
  }
}
```

### Error Response
```json
{
  "success": false,
  "timestamp": "2024-01-15T10:30:45.123456",
  "error_code": "INVALID_CONGESTION_LEVEL",
  "message": "Congestion level 'INVALID' is invalid",
  "details": {
    "provided": "INVALID",
    "valid_options": ["LOW", "MEDIUM", "HIGH"]
  }
}
```

---

## ⚙️ Configuration

### config/config.py
Central configuration file with sections:
- Application settings
- Server configuration
- ML model paths and parameters
- PSO optimizer settings
- JWT authentication
- Logging configuration
- CORS settings

### Environment Variables
```bash
export ENVIRONMENT=production
export DEBUG=False
export LOG_LEVEL=INFO
export PORT=5000
export PSO_N_PARTICLES=30
export PSO_N_ITERATIONS=50
```

### Runtime Settings
Modify settings via `/api/settings` endpoint or edit `config/settings.json`

---

## 🧪 Testing

### Install Test Dependencies (included in requirements.txt)
```bash
pip install pytest pytest-cov pytest-flask
```

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test File
```bash
pytest tests/test_auth.py -v
```

### Generate Coverage Report
```bash
pytest tests/ --cov=api --cov=services --cov=utils --cov-report=html
```

### Test Files
- `test_auth.py` - Authentication and authorization (16 tests)
- `test_endpoints.py` - API endpoints (15 tests)
- `test_services.py` - Service layer (8 tests)
- `conftest.py` - Fixtures and configuration

---

## 📝 Example Workflows

### Workflow 1: Traffic Prediction
```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@pso.com","password":"admin123"}' \
  | jq -r '.data.access_token')

# 2. Predict traffic
curl -X POST http://localhost:5000/api/predict \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "time_step": 45,
    "hour": 8,
    "density": 0.72,
    "avg_wait_time": 38.5,
    "congestion_level": "HIGH"
  }' | jq
```

### Workflow 2: Signal Optimization
```bash
# After getting prediction, optimize signals
curl -X POST http://localhost:5000/api/optimize \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "north_vehicles": 4.55,
    "south_vehicles": 4.35,
    "east_vehicles": 4.31,
    "west_vehicles": 4.34
  }' | jq
```

### Workflow 3: Complete Operation
```bash
# Single call for both prediction and optimization
curl -X POST http://localhost:5000/api/predict-and-optimize \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "time_step": 45,
    "hour": 8,
    "density": 0.72,
    "avg_wait_time": 38.5,
    "congestion_level": "HIGH"
  }' | jq
```

---

## 📋 Logging

### Log Location
`logs/app.log`

### Log Format
```
2024-01-15 10:30:45,123 | INFO     | api.app | Server started on http://0.0.0.0:5000
2024-01-15 10:30:46,456 | DEBUG    | services.prediction_service | Making prediction for: {...}
2024-01-15 10:30:47,789 | INFO     | services.prediction_service | Prediction successful. Total vehicles: 17.55
```

### Log Levels
- DEBUG: Detailed diagnostic info
- INFO: General informational messages
- WARNING: Warning messages
- ERROR: Error conditions
- CRITICAL: Critical errors

### Log Rotation
- File size: 10 MB
- Backup count: 10 files
- Auto cleanup of old logs

---

## 🛠️ Development

### Project Structure Best Practices

```
config/        → Configuration (NO business logic)
services/      → Business logic (core features)
api/           → HTTP layer (routes, responses)
utils/         → Shared utilities (logging, errors)
tests/         → Test suites (pytest)
frontend/      → UI (HTML/CSS/JS)
```

### Adding New Endpoints

1. **Create route in `api/app.py`:**
   ```python
   @app.route("/api/new-endpoint", methods=["POST"])
   @RoleManager.require_permission("permission_name")
   def new_endpoint():
       try:
           data = request.get_json()
           # Process...
   ```

---

## 🚀 Phase 2: Enterprise Backend Platform

### NEW: Persistent Storage & Analytics

Phase 2 transforms the system into a production-grade enterprise platform with:

✅ **PostgreSQL Database** - Persistent data storage with 7 tables
✅ **Redis Caching** - Multi-level caching for performance
✅ **Celery Workers** - Background job processing (12 tasks)
✅ **Analytics Engine** - Comprehensive business intelligence
✅ **Audit Trail** - Complete compliance logging
✅ **Event System** - Event-driven architecture
✅ **Model Registry** - ML model versioning
✅ **Data Export** - Multiple formats (CSV, JSON, XLSX, PDF)

### Phase 2 Quick Start

1. **Install PostgreSQL & Redis**
   ```bash
   # macOS
   brew install postgresql redis
   
   # Ubuntu
   sudo apt-get install postgresql postgresql-contrib redis-server
   ```

2. **Create Database**
   ```bash
   psql -U postgres
   CREATE DATABASE pso_traffic;
   ```

3. **Start Services**
   ```bash
   # Terminal 1: Redis
   redis-server
   
   # Terminal 2: Flask app
   python api/app.py
   
   # Terminal 3: Workers (optional)
   celery -A workers.celery_app worker --beat
   ```

4. **Access Enterprise API**
   - Enterprise API: http://localhost:5000/api/enterprise
   - See PHASE_2_GUIDE.md for 30+ new endpoints

### Phase 2 Features

#### Datasets Management
- Upload and manage traffic datasets
- SHA256 deduplication
- Statistics tracking
- Archiving capability

#### Analytics & Insights
- Historical trend analysis
- Performance metrics
- Congestion patterns
- Hourly analytics
- Model comparison

#### Audit & Compliance
- Complete action logging
- User activity tracking
- Resource change history
- Regulatory compliance

#### System Monitoring
- Health status checks
- Performance metrics
- Resource monitoring
- System status dashboard

### Phase 2 Documentation

See `documentation/` for comprehensive guides:
- **MASTER_DEVELOPMENT_PLAN.md** - Master plan with all phases and file inventory
- **PHASE_2_GUIDE.md** - Complete feature guide (600+ lines)
- **PHASE_2_COMPLETION.md** - Implementation details

### Phase 2 Configuration

Create `.env` file:
```env
DATABASE_URL=postgresql://pso_user:pso_password@localhost:5432/pso_traffic
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0
PHASE_2_ENABLED=true
```

---

## 📞 Support & Documentation

- **Phase 1**: Original features (ML prediction, PSO optimization)
- **Phase 2**: Enterprise features (database, analytics, monitoring)
- **Full Documentation**: See `documentation/` folder
- **API Reference**: http://localhost:5000/docs

---

**Version**: 2.0 (Enterprise Edition)  
**Status**: Production Ready ✅  
**Last Updated**: 2024
           return APIResponse.success(data=result), 200
       except TrafficAPIError as e:
           response_data, status = handle_error(e)
           return response_data, status
   ```

2. **Add permission to config/config.py ROLES**

3. **Create tests in tests/test_endpoints.py**

4. **Document with Swagger schema in docstring**

### Adding New Services

1. Create file in `services/`
2. Implement with logging and error handling
3. Initialize in `api/app.py`
4. Create tests in `tests/`

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Model not found | Run `python train_model.py` |
| Port 5000 in use | Change PORT in config or `export PORT=5001` |
| JWT token expired | Get new token via POST /login |
| CORS errors | Check CORS_ORIGINS in config/config.py |
| Import errors | Install all packages: `pip install -r requirements.txt` |
| Service unavailable | Check logs in `logs/app.log` |

---

## 🚀 Deployment

### Production Checklist
- [ ] Set `ENVIRONMENT=production`
- [ ] Set `DEBUG=False`
- [ ] Generate strong `JWT_SECRET_KEY`
- [ ] Set `CORS_ORIGINS` to specific domains
- [ ] Configure logging level to INFO
- [ ] Use WSGI server (gunicorn, waitress)
- [ ] Set up reverse proxy (nginx)
- [ ] Enable HTTPS
- [ ] Set up monitoring and alerts
- [ ] Configure database (optional)

### Gunicorn Deployment
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 api.app:app
```

### Docker Deployment
```dockerfile
FROM python:3.9
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV ENVIRONMENT=production
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "api.app:app"]
```

---

## 📚 Additional Resources

- **API Documentation**: http://localhost:5000/docs
- **OpenAPI Spec**: http://localhost:5000/docs.json
- **Application Logs**: `logs/app.log`
- **Generated Reports**: `reports/`
- **Test Examples**: `tests/`
- **Configuration Reference**: `config/config.py`

---

## 📊 Model Performance

| Metric | Value |
|--------|-------|
| Model Type | Random Forest |
| Features | 5 |
| Training Samples | 9,600 |
| Test Samples | 2,400 |
| R² Score (avg) | 0.952 |
| MAE (avg) | 0.281 |

---

## 📄 License & Support

This project is provided as-is for educational and commercial use.

For questions or issues:
1. Check documentation in `/documentation`
2. Review API docs at `/docs`
3. Check logs in `/logs/app.log`
4. Review test examples in `/tests`

---

**Status**: Production Ready ✅
**Version**: 1.0.0
**Last Updated**: January 2024

