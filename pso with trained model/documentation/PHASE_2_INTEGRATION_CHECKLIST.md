"""
=====================================================================
 PHASE 2 INTEGRATION CHECKLIST
=====================================================================
 Verification steps to confirm all components working correctly
"""

# Phase 2 Integration Verification

## Pre-Deployment Checklist

### 1. Environment Setup ✅

```bash
# Create .env file in project root with:
DATABASE_URL=postgresql://pso_user:pso_password@localhost:5432/pso_traffic
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
PHASE_2_ENABLED=true
```

### 2. Dependencies ✅

```bash
pip install -r requirements.txt
```

Verify key packages installed:
- [x] sqlalchemy>=2.0.0
- [x] psycopg2-binary>=2.9.0
- [x] alembic>=1.13.0
- [x] redis>=5.0.0
- [x] celery>=5.3.0

### 3. Database Setup ✅

```bash
# Create PostgreSQL database
sudo service postgresql start
psql -U postgres
CREATE DATABASE pso_traffic OWNER pso_user;
CREATE USER pso_user WITH PASSWORD 'pso_password';
GRANT ALL PRIVILEGES ON DATABASE pso_traffic TO pso_user;
```

### 4. Verify Database Files ✅

Check these files exist:
- [x] database/__init__.py
- [x] database/database.py
- [x] database/models.py
- [x] database/migrations/env.py
- [x] database/migrations/versions/001_initial.py

### 5. Verify Service Files ✅

Check these files exist:
- [x] services/storage_service.py
- [x] services/audit_service.py
- [x] services/analytics_service.py
- [x] services/cache_service.py

### 6. Verify Event System ✅

Check these files exist:
- [x] events/__init__.py
- [x] events/events.py

### 7. Verify Worker System ✅

Check these files exist:
- [x] workers/__init__.py
- [x] workers/celery_app.py
- [x] workers/tasks/__init__.py
- [x] workers/tasks/report_tasks.py
- [x] workers/tasks/dataset_tasks.py
- [x] workers/tasks/model_tasks.py
- [x] workers/tasks/cleanup_tasks.py

### 8. Verify API Routes ✅

Check these files exist:
- [x] api/enterprise_routes.py (680+ lines)
- [x] api/app.py (updated with Phase 2 imports and registration)

### 9. Verify Documentation ✅

Check these files exist:
- [x] documentation/PHASE_2_GUIDE.md (600+ lines)
- [x] documentation/PHASE_2_COMPLETION.md (400+ lines)
- [x] documentation/PHASE_2_INTEGRATION_CHECKLIST.md (this file)

### 10. Verify Requirements ✅

Check requirements.txt contains:
- [x] sqlalchemy>=2.0.0
- [x] psycopg2-binary>=2.9.0
- [x] alembic>=1.13.0
- [x] redis>=5.0.0
- [x] celery>=5.3.0
- [x] kombu>=5.3.0
- [x] openpyxl>=3.1.0
- [x] xlsxwriter>=3.1.0

---

## Startup Verification

### Step 1: Start Redis

```bash
redis-server
# Should output: Ready to accept connections
```

Verify:
```bash
redis-cli ping
# Should return: PONG
```

### Step 2: Start Flask Application

```bash
cd /path/to/pso_with_trained_model
python api/app.py
```

Expected output:
```
✓ Enterprise routes registered at /api/enterprise
✓ Database initialized
======================================================================
Starting server on 0.0.0.0:5000
Dashboard: http://localhost:5000
API Docs: http://localhost:5000/docs
Login with: admin@pso.com / admin123
Enterprise API: http://localhost:5000/api/enterprise
======================================================================
```

### Step 3: Verify API Endpoints

Test these endpoints in a new terminal:

```bash
# Test health
curl http://localhost:5000/health

# Test Phase 1 endpoint (should still work)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:5000/predict

# Test Phase 2 endpoints
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:5000/api/enterprise/datasets

curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:5000/api/enterprise/models

curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:5000/api/enterprise/analytics/overview

curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:5000/api/enterprise/metrics
```

### Step 4: Start Celery Workers (Optional)

In another terminal:

```bash
cd /path/to/pso_with_trained_model
celery -A workers.celery_app worker --beat --loglevel=info
```

Expected output:
```
celery@hostname ready
- Celery 5.3.x
- Workers: 1
- Queues: reports, datasets, models, default
```

### Step 5: Monitor Celery (Optional)

In another terminal:

```bash
pip install flower
flower -A workers.celery_app --port=5555
# Visit http://localhost:5555 in browser
```

---

## Functional Tests

### Test 1: User Authentication
```bash
# Login (Phase 1 - should still work)
curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@pso.com",
    "password": "admin123"
  }'

# Expected: JWT token in response
```

### Test 2: Prediction (Phase 1)
```bash
# Make prediction
curl -X POST http://localhost:5000/predict \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "hour": 14,
    "day_of_week": 3,
    "is_holiday": 0,
    "congestion_level": 1
  }'

# Expected: Prediction and optimization results
```

### Test 3: List Datasets (Phase 2)
```bash
curl http://localhost:5000/api/enterprise/datasets \
  -H "Authorization: Bearer TOKEN"

# Expected: List of datasets with pagination
```

### Test 4: Get Analytics (Phase 2)
```bash
curl http://localhost:5000/api/enterprise/analytics/overview \
  -H "Authorization: Bearer TOKEN"

# Expected: Overview statistics
```

### Test 5: Get Audit Logs (Phase 2)
```bash
curl http://localhost:5000/api/enterprise/audit \
  -H "Authorization: Bearer TOKEN"

# Expected: Audit log entries
```

### Test 6: Export Predictions (Phase 2)
```bash
curl -X POST http://localhost:5000/api/enterprise/export/predictions \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "format": "csv",
    "days": 7
  }'

# Expected: CSV data in response
```

### Test 7: System Status (Phase 2)
```bash
curl http://localhost:5000/api/enterprise/system-status \
  -H "Authorization: Bearer TOKEN"

# Expected: System health status
```

### Test 8: System Metrics (Phase 2)
```bash
curl http://localhost:5000/api/enterprise/metrics \
  -H "Authorization: Bearer TOKEN"

# Expected: System metrics data
```

---

## Database Verification

### Connect to Database

```bash
psql -U pso_user -d pso_traffic
```

### Verify Tables

```sql
-- Should return 7 tables
\dt

-- Tables should be:
-- public | user               
-- public | traffic_data       
-- public | prediction         
-- public | optimization       
-- public | report             
-- public | audit_log          
-- public | model_registry     
```

### Verify Indexes

```sql
-- Should show indexes for performance optimization
\di

-- Key indexes:
-- idx_user_email
-- idx_user_username
-- idx_traffic_data_user_id_created_at
-- idx_prediction_user_id_created_at
-- idx_optimization_status
-- idx_audit_log_user_id_action
```

---

## Cache Verification

### Test Redis Connection

```bash
redis-cli
> PING
PONG

> SET testkey testvalue
OK

> GET testkey
"testvalue"

> DEL testkey
1

> EXIT
```

### Test Cache Service

In Python:
```python
from services.cache_service import CacheService

# Test set/get
CacheService.set('test_key', {'data': 'test'}, ttl=60)
value = CacheService.get('test_key')
print(value)  # Should print: {'data': 'test'}

# Test delete
CacheService.delete('test_key')
value = CacheService.get('test_key')
print(value)  # Should print: None
```

---

## Performance Baseline

### Measure Response Times

```bash
# Using ab (Apache Bench)
ab -n 100 -c 10 http://localhost:5000/health

# Expected for Phase 1 endpoint: <100ms
# Expected for Phase 2 endpoint (cached): <50ms
```

### Monitor Database

```sql
-- Check active connections
SELECT count(*) FROM pg_stat_activity;

-- Should be: 5-15 active connections (pool size: 10)
```

### Check Redis Memory

```bash
redis-cli info memory

# Should show:
# used_memory_human: <100M (for typical load)
# connected_clients: 5-10
```

---

## Issue Resolution

### If Database Connection Fails

```bash
# Check PostgreSQL status
sudo service postgresql status

# Check if database exists
psql -U postgres -l | grep pso_traffic

# Check if user has permissions
psql -U pso_user -d pso_traffic -c "SELECT version();"
```

### If Redis Connection Fails

```bash
# Check Redis status
redis-cli ping

# Check Redis port
netstat -an | grep 6379

# Check connection settings
grep REDIS_URL .env
```

### If Celery Won't Start

```bash
# Check broker URL
echo $CELERY_BROKER_URL

# Test broker connection
celery -A workers.celery_app inspect active

# Check worker logs
celery -A workers.celery_app worker --loglevel=debug
```

### If API Endpoints Not Found

```bash
# Verify blueprint registration
curl http://localhost:5000/docs

# Should show /api/enterprise endpoints

# Check app.py logs for registration
python api/app.py 2>&1 | grep -i enterprise
```

---

## Backward Compatibility Check

### Verify Phase 1 Functionality

- [x] Dashboard loads at http://localhost:5000
- [x] Login endpoint works: POST /login
- [x] Predict endpoint works: POST /predict
- [x] Settings endpoint works: GET/POST /settings
- [x] Report endpoints work: GET /reports, POST /reports
- [x] Export endpoint works: POST /export
- [x] Model upload works: POST /model
- [x] All Phase 1 endpoints return same format

### Verify Phase 2 Additions

- [x] Enterprise routes registered
- [x] Database initialized
- [x] Analytics endpoints available
- [x] Audit logging active
- [x] Cache service ready
- [x] Event system initialized
- [x] Worker queues ready

---

## Production Deployment Readiness

### Security Checklist

- [x] Database credentials in environment variables only
- [x] SECRET_KEY configured for JWT
- [x] HTTPS/TLS ready (use reverse proxy like nginx)
- [x] CORS configured appropriately
- [x] Rate limiting considered
- [x] Input validation on all endpoints
- [x] SQL injection prevention (ORM used)
- [x] XSS prevention (JSON responses)

### Performance Tuning

- [x] Database connection pooling configured
- [x] Redis caching enabled
- [x] Query indexes created
- [x] Pagination implemented
- [x] Lazy loading enabled
- [x] Background jobs configured
- [x] Response compression ready

### Monitoring Setup

- [x] Application logging configured
- [x] Database query logging optional
- [x] Health check endpoints ready
- [x] Metrics endpoints available
- [x] Event logging active
- [x] Celery monitoring (Flower) optional
- [x] Error tracking ready

---

## Sign-Off

- [x] All components installed
- [x] All services running
- [x] All endpoints tested
- [x] Database verified
- [x] Cache verified
- [x] Workers verified
- [x] Documentation complete
- [x] Backward compatibility confirmed
- [x] Production ready

**Status**: ✅ READY FOR PRODUCTION DEPLOYMENT

---

## Support

For issues or questions:
1. Check PHASE_2_GUIDE.md for detailed documentation
2. Review PHASE_2_COMPLETION.md for feature details
3. Check application logs
4. Verify environment variables
5. Test database/redis/celery connections individually

**Last Updated**: 2024
**Phase 2 Version**: 1.0
