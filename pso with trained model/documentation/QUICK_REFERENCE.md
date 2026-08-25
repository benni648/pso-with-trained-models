"""
=====================================================================
 QUICK REFERENCE GUIDE
=====================================================================
 Quick lookup for common tasks and commands.
=====================================================================
"""

# PSO Traffic System - Quick Reference Guide

## 🚀 Quick Start (30 seconds)

```bash
# 1. Run the application
python api/app.py

# 2. Open dashboard
http://localhost:5000

# 3. Login (admin account)
Email: admin@pso.com
Password: admin123

# 4. View API docs
http://localhost:5000/docs
```

## 📂 Key Files & Locations

| Component | File | Purpose |
|-----------|------|---------|
| Configuration | `config/config.py` | All settings in one place |
| Logging | `utils/logger.py` | Structured logging |
| Errors | `utils/errors.py` | Custom exceptions |
| Responses | `utils/response.py` | Standardized JSON responses |
| Authentication | `utils/auth.py` | JWT & RBAC |
| Health | `utils/health.py` | System monitoring |
| Predictions | `services/prediction_service.py` | ML prediction wrapper |
| Optimization | `services/optimization_service.py` | PSO wrapper |
| Reports | `services/report_service.py` | Report generation |
| Settings | `services/settings_service.py` | Runtime settings |
| App | `api/app.py` | Main Flask application |
| Tests | `tests/` | Test suite |
| Dashboard | `frontend/` | Web UI |
| Logs | `logs/app.log` | Application logs |
| Reports | `reports/` | Generated reports |

## 🔐 Default Users

```
Admin:
  Email: admin@pso.com
  Password: admin123
  Role: ADMIN (full access)

Operator:
  Email: operator@pso.com
  Password: operator123
  Role: TRAFFIC_OPERATOR (predict, optimize)

Viewer:
  Email: viewer@pso.com
  Password: viewer123
  Role: VIEWER (predict only)
```

## 🔗 Important URLs

| URL | Purpose |
|-----|---------|
| http://localhost:5000 | Dashboard |
| http://localhost:5000/docs | API documentation |
| http://localhost:5000/api/health | Health status |
| http://localhost:5000/login | Login endpoint |
| http://localhost:5000/api/predict | Prediction API |
| http://localhost:5000/api/optimize | Optimization API |
| http://localhost:5000/api/settings | Settings API |

## 📋 Common Commands

### Installation & Setup
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate.bat # Windows

# Install dependencies
pip install -r requirements.txt

# Run application
python api/app.py

# Run with Gunicorn (production)
gunicorn -w 4 -b 0.0.0.0:5000 api.app:app
```

### Testing
```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_auth.py -v

# Generate coverage report
pytest tests/ --cov=api --cov=services --cov=utils
```

### Logging & Debugging
```bash
# View logs
tail -f logs/app.log

# Search logs for errors
grep ERROR logs/app.log

# Clear logs
rm logs/app.log
```

### Configuration
```bash
# Change port
export PORT=8000

# Change log level
export LOG_LEVEL=DEBUG

# Disable authentication
export JWT_ENABLED=False
```

### API Testing
```bash
# Get token
curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@pso.com","password":"admin123"}'

# Test prediction
curl -X POST http://localhost:5000/api/predict \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"time_step":45,"hour":8,"density":0.72,"avg_wait_time":38.5,"congestion_level":"HIGH"}'

# Check health
curl http://localhost:5000/api/health
```

## 📊 API Endpoints

### Authentication
- `POST /login` - Get JWT token
- `POST /logout` - Logout
- `POST /refresh` - Refresh token

### Traffic Operations
- `POST /api/predict` - Predict traffic
- `POST /api/optimize` - Optimize signals
- `POST /api/predict-and-optimize` - Combined

### System
- `GET /api/health` - Health status
- `GET /api/settings` - Get settings
- `POST /api/settings` - Update settings (admin)

### Reports
- `POST /api/generate-report` - Generate report
- `GET /api/reports` - List reports

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| Module not found | `pip install -r requirements.txt` |
| Port in use | `export PORT=8000` |
| Model not found | `python train_model.py` |
| JWT error | Get new token via POST /login |
| CORS error | Check CORS_ORIGINS in config |
| Import error | Check Python path: `sys.path.insert(0, os.path.dirname(__file__))` |

## 🔧 Configuration Parameters

| Parameter | Default | Location |
|-----------|---------|----------|
| PORT | 5000 | config/config.py |
| HOST | 0.0.0.0 | config/config.py |
| DEBUG | False | config/config.py |
| LOG_LEVEL | INFO | config/config.py |
| JWT_ENABLED | True | config/config.py |
| PSO_N_PARTICLES | 30 | config/config.py |
| PSO_N_ITERATIONS | 50 | config/config.py |
| CORS_ORIGINS | * | config/config.py |

## 📈 Performance Tips

| Goal | Action |
|------|--------|
| Faster response | Reduce PSO_N_PARTICLES to 20 |
| Better accuracy | Increase PSO_N_ITERATIONS to 100 |
| Lower memory | Disable CACHE or reduce CACHE_TTL |
| Higher throughput | Use Gunicorn with -w 8 workers |
| Production ready | Set DEBUG=False, JWT_ENABLED=True |

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| README.md | Overview and getting started |
| MIGRATION_GUIDE.md | Academic → Professional migration |
| ARCHITECTURE.md | System design and components |
| SETUP_GUIDE.md | Complete setup and deployment |
| FRONTEND_ENHANCEMENTS.md | UI/UX improvements |

## 🔒 Security Checklist

- [ ] Change default passwords
- [ ] Generate strong JWT_SECRET_KEY
- [ ] Enable HTTPS in production
- [ ] Restrict CORS_ORIGINS
- [ ] Set DEBUG=False
- [ ] Configure firewall rules
- [ ] Enable rate limiting
- [ ] Set up backups
- [ ] Enable monitoring
- [ ] Regular security updates

## 📦 Dependencies

### Core ML
- scikit-learn (ML models)
- pandas (data processing)
- numpy (numerical computing)

### Web Framework
- flask (web server)
- flask-cors (CORS support)
- flasgger (API documentation)

### Authentication
- pyjwt (JWT tokens)

### Monitoring
- psutil (system metrics)

### Testing
- pytest (test framework)

### Optional
- gunicorn (production server)
- reportlab (PDF generation)

## 🎯 Common Workflows

### Workflow 1: Development
```bash
export ENVIRONMENT=development
export DEBUG=True
export LOG_LEVEL=DEBUG
export JWT_ENABLED=False
python api/app.py
```

### Workflow 2: Testing
```bash
export ENVIRONMENT=testing
pytest tests/ -v
```

### Workflow 3: Production
```bash
export ENVIRONMENT=production
export DEBUG=False
export JWT_ENABLED=True
gunicorn -w 4 -b 0.0.0.0:5000 api.app:app
```

### Workflow 4: Model Retraining
```bash
python train_model.py
python api/app.py  # Restart to load new model
```

## 🆘 Getting Help

1. **Check Documentation**
   - README.md - Overview
   - SETUP_GUIDE.md - Installation
   - ARCHITECTURE.md - Design

2. **Review Logs**
   ```bash
   tail -f logs/app.log
   grep ERROR logs/app.log
   ```

3. **Test API**
   ```bash
   curl http://localhost:5000/api/health
   ```

4. **Run Tests**
   ```bash
   pytest tests/ -v
   ```

5. **Check Configuration**
   - config/config.py
   - Environment variables
   - Settings file (config/settings.json)

## 📞 Support Contacts

For issues with:
- **ML Model**: Check train_model.py or model_meta.json
- **Optimization**: Review pso_integration.py and PSO parameters
- **API**: Visit http://localhost:5000/docs
- **Frontend**: Check browser console for errors
- **Authentication**: Verify JWT_SECRET_KEY and credentials

## ⚡ Performance Baselines

| Operation | Time | Throughput |
|-----------|------|-----------|
| Prediction | ~100ms | 10/sec |
| Optimization | ~500ms | 2/sec |
| Combined | ~600ms | 1-2/sec |
| Health Check | ~10ms | 100/sec |
| Token Refresh | ~20ms | 50/sec |

## 📅 Maintenance Schedule

### Daily
- Check logs for errors
- Monitor resource usage
- Verify API availability

### Weekly
- Review performance metrics
- Check for security alerts
- Backup reports and logs

### Monthly
- Analyze traffic patterns
- Review PSO parameters
- Retrain model if needed
- Update dependencies

### Quarterly
- Performance audit
- Security review
- Capacity planning
- Documentation update

---

**Status**: Complete Reference ✅
**Last Updated**: January 2024
**Version**: 1.0.0
