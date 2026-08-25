"""
=====================================================================
 Complete Setup & Integration Guide
=====================================================================
 Step-by-step guide to deploy the professional edition.
=====================================================================
"""

# Complete Setup & Integration Guide

## Pre-Deployment Checklist

### System Requirements
- [ ] Python 3.8 or higher installed
- [ ] pip package manager available
- [ ] 500 MB free disk space
- [ ] Network connectivity (optional, for package download)
- [ ] Git (optional, for version control)

### Project Files
- [ ] `predict_traffic.py` present
- [ ] `pso_integration.py` present
- [ ] `train_model.py` present
- [ ] `saved_models/rf_model.pkl` exists
- [ ] `pso_traffic_preprocessed.csv` present
- [ ] `frontend/pso_traffic_dashboard_connected.html` present

## Installation Steps

### Step 1: Navigate to Project Directory
```bash
cd "C:\Users\...\pso with trained model"
# or on Linux/Mac
cd ~/path/to/pso\ with\ trained\ model
```

### Step 2: Create Python Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate.bat
```

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt.

### Step 3: Install All Dependencies
```bash
pip install -r requirements.txt
```

This installs:
- Flask, Flasgger (web framework + API docs)
- scikit-learn, pandas, numpy (ML dependencies)
- PyJWT (authentication)
- psutil (system monitoring)
- pytest (testing framework)

**Installation time:** 2-5 minutes (depending on internet speed)

### Step 4: Verify Installation
```bash
python -c "from api.app import app; print('✓ App imports successfully')"
```

Expected output: `✓ App imports successfully`

## Running the Application

### Option 1: Using Run Script (Recommended)

**Windows:**
```bash
run.bat
```

**Linux/Mac:**
```bash
chmod +x run.sh
./run.sh
```

The script will:
1. Create virtual environment (if needed)
2. Activate virtual environment
3. Install dependencies
4. Start the server

### Option 2: Manual Start

```bash
python api/app.py
```

### Option 3: Production Start (with Gunicorn)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 api.app:app
```

## Accessing the Application

### Application URLs
- **Dashboard**: http://localhost:5000
- **API Documentation**: http://localhost:5000/docs
- **Health Check**: http://localhost:5000/api/health
- **Login**: Direct login via dashboard or use API

### Default Credentials
```
Role: ADMIN
Email: admin@pso.com
Password: admin123

Role: TRAFFIC_OPERATOR
Email: operator@pso.com
Password: operator123

Role: VIEWER
Email: viewer@pso.com
Password: viewer123
```

## Quick Start Workflow

### 1. Start Server
```bash
python api/app.py
```

### 2. Get Authentication Token
```bash
# Linux/Mac
TOKEN=$(curl -s -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@pso.com","password":"admin123"}' \
  | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

echo "Token: $TOKEN"
```

### 3. Test Prediction Endpoint
```bash
curl -X POST http://localhost:5000/api/predict \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "time_step": 45,
    "hour": 8,
    "density": 0.72,
    "avg_wait_time": 38.5,
    "congestion_level": "HIGH"
  }' | python -m json.tool
```

### 4. Test Optimization Endpoint
```bash
curl -X POST http://localhost:5000/api/optimize \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "north_vehicles": 4.55,
    "south_vehicles": 4.35,
    "east_vehicles": 4.31,
    "west_vehicles": 4.34
  }' | python -m json.tool
```

## Running Tests

### Install Test Dependencies
Already included in requirements.txt!

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test Module
```bash
pytest tests/test_auth.py -v
pytest tests/test_endpoints.py -v
pytest tests/test_services.py -v
```

### Generate Coverage Report
```bash
pytest tests/ --cov=api --cov=services --cov=utils --cov-report=html
# Open htmlcov/index.html in browser
```

## Configuration Customization

### Change API Port
**Option 1: Environment Variable**
```bash
export PORT=8000
python api/app.py
```

**Option 2: Edit config/config.py**
```python
PORT = 8000
```

### Change Log Level
```bash
export LOG_LEVEL=DEBUG
python api/app.py
```

### Disable Authentication
Edit `config/config.py`:
```python
JWT_ENABLED = False
```

### Add Custom Users
Edit `utils/auth.py`:
```python
DEMO_USERS = {
    "youruser@pso.com": {
        "password": "yourpassword",
        "role": "ADMIN",
        "name": "Your Name"
    }
}
```

### Adjust PSO Parameters
Edit `config/config.py`:
```python
PSO_N_PARTICLES = 50       # More particles = better but slower
PSO_N_ITERATIONS = 100     # More iterations = better but slower
PSO_BOUNDS_MIN = 10        # Minimum signal duration
PSO_BOUNDS_MAX = 90        # Maximum signal duration
```

## Troubleshooting

### Issue: Module not found
```
Error: ModuleNotFoundError: No module named 'flask'
Solution: Install dependencies: pip install -r requirements.txt
```

### Issue: Port already in use
```
Error: Address already in use
Solution: 
  - Change port: export PORT=5001
  - Or kill existing process using port 5000
```

### Issue: Model not found
```
Error: Model not found at 'saved_models/rf_model.pkl'
Solution: Train model first: python train_model.py
```

### Issue: JWT token errors
```
Error: Invalid token or Authentication failed
Solution: Get new token: curl -X POST http://localhost:5000/login ...
```

### Issue: CORS errors in browser
```
Error: CORS policy: ...
Solution: Check CORS_ORIGINS in config/config.py
```

### Issue: Database connection error (future)
```
Error: Cannot connect to database
Solution: Configure DATABASE_URL in config/config.py
```

## Environment Setup Examples

### Development Environment
```bash
export ENVIRONMENT=development
export DEBUG=True
export LOG_LEVEL=DEBUG
export JWT_ENABLED=False
export CORS_ORIGINS="*"
python api/app.py
```

### Production Environment
```bash
export ENVIRONMENT=production
export DEBUG=False
export LOG_LEVEL=INFO
export JWT_ENABLED=True
export CORS_ORIGINS="https://yourdomain.com,https://api.yourdomain.com"
export JWT_SECRET_KEY="your-secret-key-min-32-chars"
gunicorn -w 4 -b 0.0.0.0:5000 api.app:app
```

### Testing Environment
```bash
export ENVIRONMENT=testing
export DEBUG=True
export LOG_LEVEL=DEBUG
export JWT_ENABLED=True
export RATE_LIMIT_ENABLED=False
pytest tests/ -v
```

## Docker Deployment (Optional)

### Create Dockerfile
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 5000

# Set environment
ENV ENVIRONMENT=production
ENV DEBUG=False

# Run application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "api.app:app"]
```

### Build Docker Image
```bash
docker build -t pso-traffic:1.0 .
```

### Run Docker Container
```bash
docker run -p 5000:5000 \
  -e JWT_SECRET_KEY="your-secret-key" \
  -e LOG_LEVEL="INFO" \
  pso-traffic:1.0
```

## Performance Tuning

### For High Traffic Load
```python
# config/config.py
PSO_N_PARTICLES = 20       # Reduce from 30 for speed
PSO_N_ITERATIONS = 25      # Reduce from 50 for speed
CACHE_ENABLED = True
CACHE_TTL = 600            # Increase to 10 minutes
```

### For High Accuracy
```python
# config/config.py
PSO_N_PARTICLES = 50       # Increase for better solutions
PSO_N_ITERATIONS = 100     # Increase for convergence
CACHE_ENABLED = False      # Disable to avoid stale predictions
```

### For Development/Testing
```python
# config/config.py
RATE_LIMIT_ENABLED = False
JWT_ENABLED = False        # For quick testing
LOG_LEVEL = "DEBUG"
```

## Monitoring & Logging

### View Application Logs
```bash
# Real-time logs
tail -f logs/app.log

# Last 50 lines
tail -50 logs/app.log

# Search for errors
grep ERROR logs/app.log
```

### Check System Health
```bash
curl http://localhost:5000/api/health | python -m json.tool
```

### Monitor Performance
```bash
# Watch CPU and memory
# Linux/Mac
watch -n 1 'ps aux | grep python'

# Windows
Get-Process python
```

## Backup & Recovery

### Backup Application
```bash
# Backup everything
tar -czf pso-traffic-backup-$(date +%Y%m%d).tar.gz \
  api/ services/ config/ utils/ tests/ logs/ reports/

# Backup logs only
tar -czf pso-traffic-logs-$(date +%Y%m%d).tar.gz logs/

# Backup reports only
tar -czf pso-traffic-reports-$(date +%Y%m%d).tar.gz reports/
```

### Restore from Backup
```bash
tar -xzf pso-traffic-backup-20240115.tar.gz
```

## Scaling Considerations

### Horizontal Scaling
For multiple servers, consider:
1. Load balancer (nginx, HAProxy)
2. Shared database for settings
3. Shared cache (Redis)
4. Centralized logging (ELK stack)

### Vertical Scaling
For single server, consider:
1. More CPU cores: Increase Gunicorn workers (`-w 8`)
2. More RAM: Increase cache TTL and model batch size
3. SSD storage: For faster log I/O

## Security Hardening

### Before Production Deployment
- [ ] Change all default passwords
- [ ] Generate strong JWT_SECRET_KEY
- [ ] Enable HTTPS/SSL
- [ ] Restrict CORS_ORIGINS
- [ ] Set up firewall rules
- [ ] Enable rate limiting
- [ ] Configure backup strategy
- [ ] Set up monitoring/alerting

### Generate Secure JWT Key
```bash
# Linux/Mac
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Windows
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Maintenance Tasks

### Daily
- [ ] Monitor logs for errors
- [ ] Check system resources
- [ ] Verify API availability

### Weekly
- [ ] Review logs and metrics
- [ ] Backup reports and logs
- [ ] Update dependencies (if applicable)

### Monthly
- [ ] Analyze traffic patterns
- [ ] Review and optimize PSO parameters
- [ ] Retrain ML model if needed
- [ ] Generate performance reports

## Support & Documentation

- **API Docs**: http://localhost:5000/docs
- **README**: Root directory README.md
- **Migration Guide**: documentation/MIGRATION_GUIDE.md
- **Architecture**: documentation/ARCHITECTURE.md
- **Logs**: logs/app.log

---

**Setup Status**: Complete ✅
**Ready to Deploy**: Yes ✅
**Estimated Setup Time**: 10-15 minutes ✅
