"""
=====================================================================
 PHASE 2 QUICK START GUIDE
=====================================================================
 Get the system running in 5 minutes
"""

# Phase 2 - Quick Start Guide

## ⚡ 5-Minute Startup

### Prerequisites
- Python 3.8+
- PostgreSQL 12+
- Redis 5.0+

### Step 1: Install Dependencies (1 min)

```bash
cd /path/to/pso_with_trained_model
pip install -r requirements.txt
```

### Step 2: Setup PostgreSQL (1 min)

```bash
# Create database
psql -U postgres

# In PostgreSQL:
CREATE DATABASE pso_traffic;
CREATE USER pso_user WITH PASSWORD 'pso_password';
GRANT ALL PRIVILEGES ON DATABASE pso_traffic TO pso_user;
\q
```

### Step 3: Create Environment File (1 min)

Create `.env` file in project root:

```env
DATABASE_URL=postgresql://pso_user:pso_password@localhost:5432/pso_traffic
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
PHASE_2_ENABLED=true
```

### Step 4: Start Services (2 min)

#### Terminal 1 - Redis
```bash
redis-server
# Output: Ready to accept connections
```

#### Terminal 2 - Flask App
```bash
cd /path/to/pso_with_trained_model
python api/app.py

# Output should show:
# ✓ Enterprise routes registered at /api/enterprise
# ✓ Database initialized
# Starting server on 0.0.0.0:5000
```

#### Terminal 3 - Celery Workers (Optional)
```bash
cd /path/to/pso_with_trained_model
celery -A workers.celery_app worker --beat --loglevel=info
```

### Step 5: Test System

```bash
# Test health
curl http://localhost:5000/health

# Test Phase 1 (login)
curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@pso.com",
    "password": "admin123"
  }'

# Test Phase 2 (datasets)
curl http://localhost:5000/api/enterprise/datasets \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🌐 Access Points

Once running:

| Component | URL | Purpose |
|-----------|-----|---------|
| Dashboard | http://localhost:5000 | Main UI |
| API Enterprise | http://localhost:5000/api/enterprise | Phase 2 API |
| API Docs | http://localhost:5000/docs | Swagger UI |
| Redis | localhost:6379 | Cache |
| Celery | (command line) | Workers |
| Flower (optional) | http://localhost:5555 | Worker monitoring |

## 🔧 Common Commands

### Flask Application

```bash
# Start app
python api/app.py

# Run in production (with gunicorn)
gunicorn -w 4 -b 0.0.0.0:5000 api.app:app

# Run tests
pytest tests/ -v

# Database migrations
cd database/migrations
alembic upgrade head
alembic downgrade -1
```

### Redis

```bash
# Start Redis
redis-server

# Monitor connections
redis-cli info

# Flush cache (careful!)
redis-cli FLUSHALL

# Check specific key
redis-cli GET prediction:123
```

### Celery Workers

```bash
# Start default worker
celery -A workers.celery_app worker --loglevel=info

# With beat scheduler (periodic tasks)
celery -A workers.celery_app worker --beat --loglevel=info

# Specific queues only
celery -A workers.celery_app worker -Q reports,datasets

# Monitor (in another terminal)
celery -A workers.celery_app inspect active

# Flower web UI
pip install flower
flower -A workers.celery_app --port=5555
```

### Database

```bash
# Connect to database
psql -U pso_user -d pso_traffic

# View all tables
\dt

# View table structure
\d prediction

# Exit
\q

# Database operations
python -c "from api.app import app; from database import init_db; init_db()"
```

## 📊 API Examples

### Authentication

```bash
# Login
curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@pso.com",
    "password": "admin123"
  }'

# Response:
# {"token": "eyJ0eXAiOiJKV1QiLCJhbGc...", "user": {...}}

# Use token in headers
export TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."
```

### Phase 2 Endpoints

```bash
# List datasets
curl http://localhost:5000/api/enterprise/datasets \
  -H "Authorization: Bearer $TOKEN"

# Get analytics
curl http://localhost:5000/api/enterprise/analytics/overview \
  -H "Authorization: Bearer $TOKEN"

# Export predictions
curl -X POST http://localhost:5000/api/enterprise/export/predictions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"format": "csv", "days": 7}'

# Get audit logs
curl http://localhost:5000/api/enterprise/audit \
  -H "Authorization: Bearer $TOKEN"

# System status
curl http://localhost:5000/api/enterprise/system-status \
  -H "Authorization: Bearer $TOKEN"
```

## 🆘 Troubleshooting

### Connection Issues

```bash
# PostgreSQL not running
sudo service postgresql start  # Linux
brew services start postgresql  # macOS

# Redis not running
redis-server

# Test connections
psql -U postgres -c "SELECT version();"
redis-cli ping
```

### Import Errors

```bash
# If getting "No module named 'database'"
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python api/app.py

# Or install in development mode
pip install -e .
```

### Database Issues

```bash
# Reset database
psql -U postgres
DROP DATABASE pso_traffic;
CREATE DATABASE pso_traffic;
\q

# Then restart app - it will recreate schema
python api/app.py
```

### Worker Issues

```bash
# Check if broker running
redis-cli ping

# Verify Celery config
python -c "from workers.celery_app import app; print(app.conf)"

# Run worker in foreground to see errors
celery -A workers.celery_app worker --loglevel=debug
```

## 📈 Performance Tips

### Caching
- Ensure Redis is running
- Check Redis memory: `redis-cli info memory`
- Clear cache if needed: `redis-cli FLUSHALL`

### Database
- Check connection pool: Pool(size=10, overflow=20)
- Monitor queries: `psql -U pso_user -d pso_traffic`
- Run `ANALYZE` periodically: `psql -U pso_user -d pso_traffic -c "ANALYZE;"`

### Workers
- Run multiple workers: `-c 4` (4 concurrent tasks)
- Monitor with Flower: `flower -A workers.celery_app`
- Check queue depth: `celery -A workers.celery_app inspect active`

## 🔒 Security Tips

### Passwords
- Change default password in config
- Use environment variables
- Never commit secrets

### Database
```bash
# Enable password authentication
sudo -u postgres psql
ALTER USER pso_user WITH ENCRYPTED PASSWORD 'strong_password';
```

### API
- Always use SSL/TLS in production
- Use reverse proxy (nginx)
- Rate limiting recommended
- Input validation enabled

## 📚 More Information

See documentation in `documentation/`:
- **PHASE_2_GUIDE.md** - Comprehensive guide
- **PHASE_2_INTEGRATION_CHECKLIST.md** - Detailed setup
- **API_REFERENCE.md** - All endpoints

## ✅ Verification Checklist

- [ ] Python packages installed
- [ ] PostgreSQL running and database created
- [ ] Redis running
- [ ] Flask app starts without errors
- [ ] Can access http://localhost:5000
- [ ] Can login with admin@pso.com
- [ ] Phase 2 endpoints accessible
- [ ] Celery workers running (optional)
- [ ] Flower monitoring (optional)

---

**Ready to go!** 🚀

If anything doesn't work, check the troubleshooting section or see the full documentation.
