"""
=====================================================================
 PHASE 2: ENTERPRISE BACKEND PLATFORM
=====================================================================
 Complete transformation from Phase 1 to production-grade backend.
"""

# Phase 2 - Enterprise Backend Platform

## Overview

Phase 2 transforms the PSO Traffic System into a production-grade enterprise backend platform with persistent storage, advanced analytics, scalability, and monitoring capabilities.

### What's New

✅ **Persistent Database Layer** - PostgreSQL with SQLAlchemy ORM
✅ **Historical Analytics** - Track metrics over time
✅ **Caching System** - Redis for performance optimization
✅ **Background Jobs** - Celery for async processing
✅ **Audit Trail** - Complete action logging
✅ **Event System** - Event-driven architecture foundation
✅ **Model Registry** - Track ML model versions
✅ **Data Export** - Multiple export formats
✅ **System Monitoring** - Health checks and metrics

---

## Architecture Overview

### Layered Architecture

```
┌─────────────────────────────────────┐
│   REST API Layer                    │
│   (/api/enterprise/*)               │
├─────────────────────────────────────┤
│   Service Layer                     │
│   - Analytics, Audit, Storage       │
│   - Cache, Events                   │
├─────────────────────────────────────┤
│   Data Layer                        │
│   - PostgreSQL Database             │
│   - Redis Cache                     │
│   - File Storage                    │
├─────────────────────────────────────┤
│   Background Workers                │
│   - Celery Tasks                    │
│   - Report Generation               │
│   - Model Training                  │
└─────────────────────────────────────┘
```

### Component Details

#### 1. Database Layer (`database/`)

**Files:**
- `database.py` - Connection management, session handling
- `models.py` - SQLAlchemy ORM models
- `migrations/` - Alembic schema migrations

**Models:**
- `User` - System users with roles
- `TrafficData` - Uploaded datasets
- `Prediction` - ML prediction records
- `Optimization` - PSO execution records
- `Report` - Generated reports
- `AuditLog` - Action audit trail
- `ModelRegistry` - ML model versioning

**Features:**
- Connection pooling (10 active, 20 max)
- Automatic connection recycling
- Transaction management
- Health check monitoring

#### 2. Storage Service (`services/storage_service.py`)

**Methods:**
```python
StorageService.upload_dataset()          # Upload new dataset
StorageService.get_dataset()             # Retrieve dataset
StorageService.get_datasets()            # List datasets with pagination
StorageService.delete_dataset()          # Delete dataset
StorageService.archive_dataset()         # Archive old dataset
StorageService.get_dataset_statistics()  # Get dataset statistics
```

**Features:**
- SHA256 deduplication
- File size tracking
- Statistics calculation
- Automatic archiving

#### 3. Audit Service (`services/audit_service.py`)

**Methods:**
```python
AuditService.log_action()                # Log any action
AuditService.get_user_audit_logs()       # Get user's actions
AuditService.get_action_audit_logs()     # Get actions of a type
AuditService.get_resource_audit_logs()   # Get resource changes
AuditService.log_login()                 # Log user login
AuditService.log_logout()                # Log user logout
AuditService.log_dataset_upload()        # Log dataset upload
AuditService.log_prediction()            # Log prediction request
AuditService.log_optimization()          # Log optimization request
```

**Tracked Actions:**
- LOGIN / LOGOUT
- DATASET_UPLOAD / DATASET_DELETE
- PREDICTION_REQUEST
- OPTIMIZATION_REQUEST
- REPORT_GENERATION
- SETTINGS_CHANGE

#### 4. Analytics Service (`services/analytics_service.py`)

**Methods:**
```python
AnalyticsService.get_overview_stats()        # Overall metrics
AnalyticsService.get_performance_metrics()   # System performance
AnalyticsService.get_trend_analysis()        # Historical trends
AnalyticsService.get_congestion_analysis()   # Congestion patterns
AnalyticsService.get_hourly_patterns()       # Hour-by-hour analysis
AnalyticsService.get_model_comparison()      # Model performance compare
```

**Metrics:**
- Total predictions / optimizations
- Average latency / duration
- Success rates
- Fitness scores
- Congestion distribution
- Hourly patterns
- Model comparison

#### 5. Cache Service (`services/cache_service.py`)

**Redis Integration:**
```python
CacheService.set()                       # Set cache value with TTL
CacheService.get()                       # Get cached value
CacheService.delete()                    # Delete cache value
CacheService.flush()                     # Clear all cache
CacheService.get_stats()                 # Cache statistics

# Specific cache operations:
CacheService.cache_prediction()          # Cache prediction result
CacheService.cache_optimization()        # Cache optimization result
CacheService.cache_dashboard_stats()     # Cache dashboard stats
CacheService.cache_analytics()           # Cache analytics data
```

**Cache Keys:**
- `prediction:{id}` - Prediction results (1 hour TTL)
- `optimization:{id}` - Optimization results (1 hour TTL)
- `dashboard:stats` - Dashboard statistics (5 minutes TTL)
- `health:status` - Health status (1 minute TTL)
- `analytics:{key}` - Analytics data (30 minutes TTL)

**Environment:**
```bash
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0
```

#### 6. Event System (`events/`)

**Event Types:**
```python
EventType.PREDICTION_CREATED          # New prediction
EventType.OPTIMIZATION_COMPLETED      # Optimization done
EventType.DATASET_UPLOADED            # Dataset uploaded
EventType.REPORT_GENERATED            # Report generated
EventType.SETTINGS_CHANGED            # Settings updated
EventType.USER_LOGGED_IN              # User login
EventType.MODEL_ACTIVATED             # Model activated
```

**Event Publishing:**
```python
from events import EventBus, PredictionCreatedEvent

event = PredictionCreatedEvent(
    prediction_id=123,
    model_version='v1.0',
    user_id=1,
    latency_ms=150.5
)
EventBus.publish(event)
```

**Event Subscription:**
```python
from events import EventBus, EventType

def handle_prediction(event):
    print(f"Prediction created: {event.data['prediction_id']}")

EventBus.subscribe(EventType.PREDICTION_CREATED, handle_prediction)
```

#### 7. Background Workers (`workers/`)

**Task Types:**

**Report Tasks:**
- `generate_report_task()` - Generate traffic report
- `email_report_task()` - Email report to user
- `archive_old_reports_task()` - Archive reports older than N days

**Dataset Tasks:**
- `process_dataset_task()` - Process uploaded dataset
- `validate_dataset_task()` - Validate dataset quality
- `archive_old_datasets_task()` - Archive old datasets

**Model Tasks:**
- `retrain_model_task()` - Retrain ML model
- `evaluate_model_task()` - Evaluate model performance
- `backup_model_task()` - Backup model files

**Cleanup Tasks:**
- `cleanup_old_audit_logs_task()` - Delete old audit logs
- `cleanup_old_predictions_task()` - Archive old predictions
- `cleanup_temp_files_task()` - Clean temporary files
- `health_check_task()` - Periodic health check

**Running Celery:**
```bash
# Start worker
celery -A workers.celery_app worker --loglevel=info

# Start beat scheduler (for periodic tasks)
celery -A workers.celery_app beat --loglevel=info

# With multiple queues
celery -A workers.celery_app worker -Q reports,datasets,models,default --loglevel=info
```

---

## API Endpoints (Phase 2)

### Base URL: `/api/enterprise/`

### Dataset Management

**GET /datasets** - List datasets
```
Query Parameters:
  - page: int (default: 1)
  - per_page: int (default: 10)

Response:
{
  "success": true,
  "data": [
    {"id": 1, "filename": "traffic.csv", "row_count": 1000, ...}
  ],
  "meta": {"page": 1, "total": 100}
}
```

**GET /datasets/{id}** - Get dataset details
```
Response:
{
  "success": true,
  "data": {
    "id": 1,
    "filename": "traffic.csv",
    "row_count": 1000,
    "column_count": 8,
    "uploaded_at": "2024-01-01T12:00:00"
  }
}
```

**DELETE /datasets/{id}** - Delete dataset
```
Response:
{
  "success": true,
  "data": {"deleted": true}
}
```

### Prediction History

**GET /predictions/history** - Get prediction history
```
Query Parameters:
  - page: int (default: 1)
  - per_page: int (default: 10)
  - days: int (default: 7)

Response:
{
  "success": true,
  "data": [
    {
      "id": 1,
      "model_version": "v1.0",
      "latency_ms": 150.5,
      "congestion_level": "HIGH",
      "created_at": "2024-01-01T12:00:00"
    }
  ]
}
```

**GET /predictions/stats** - Get prediction statistics
```
Response:
{
  "success": true,
  "data": {
    "total_predictions": 1000,
    "successful": 950,
    "failed": 50,
    "success_rate": 95.0,
    "average_latency_ms": 145.3
  }
}
```

### Optimization History

**GET /optimizations/history** - Get optimization history
```
Query Parameters:
  - page: int (default: 1)
  - per_page: int (default: 10)
  - days: int (default: 7)

Response:
{
  "success": true,
  "data": [
    {
      "id": 1,
      "fitness_score": 0.95,
      "duration_ms": 500.2,
      "iterations_completed": 50,
      "created_at": "2024-01-01T12:00:00"
    }
  ]
}
```

**GET /optimizations/best** - Get best optimizations
```
Query Parameters:
  - limit: int (default: 10)

Response:
{
  "success": true,
  "data": [
    {"id": 1, "fitness_score": 0.99, ...}
  ]
}
```

### Analytics

**GET /analytics/overview** - Overview statistics
```
Response:
{
  "success": true,
  "data": {
    "period_days": 7,
    "total_predictions": 1000,
    "total_optimizations": 500,
    "average_prediction_latency_ms": 145.3,
    "datasets_uploaded": 10
  }
}
```

**GET /analytics/performance** - Performance metrics
```
Response:
{
  "success": true,
  "data": {
    "prediction_success_rate": 95.0,
    "optimization_success_rate": 98.0,
    "average_fitness_score": 0.92,
    "best_fitness_score": 0.99
  }
}
```

**GET /analytics/trends** - Trend analysis
```
Query Parameters:
  - days: int (default: 30)

Response:
{
  "success": true,
  "data": {
    "period_days": 30,
    "trends": [
      {
        "date": "2024-01-01",
        "predictions": 50,
        "optimizations": 25,
        "avg_fitness_score": 0.92
      }
    ]
  }
}
```

### Audit Logs

**GET /audit** - Get audit logs
```
Query Parameters:
  - page: int (default: 1)
  - per_page: int (default: 50)
  - action: string (optional)

Response:
{
  "success": true,
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "action": "PREDICTION_REQUEST",
      "resource_type": "Prediction",
      "resource_id": 123,
      "status": "SUCCESS",
      "created_at": "2024-01-01T12:00:00"
    }
  ]
}
```

### Model Registry

**GET /models** - List models
```
Response:
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "traffic_predictor",
      "version": "v1.0",
      "model_type": "RANDOM_FOREST",
      "status": "ACTIVE",
      "is_current": true
    }
  ]
}
```

**GET /models/current** - Get current model
```
Response:
{
  "success": true,
  "data": {
    "id": 1,
    "name": "traffic_predictor",
    "version": "v1.0",
    "model_type": "RANDOM_FOREST",
    "metrics": {...},
    "is_production": true
  }
}
```

**POST /models/{id}/activate** - Activate model
```
Response:
{
  "success": true,
  "data": {"activated": true}
}
```

### Data Export

**POST /export/predictions** - Export predictions
```
Body:
{
  "format": "csv|json|xlsx|pdf",
  "days": 7
}

Response:
{
  "success": true,
  "data": {
    "format": "csv",
    "count": 100,
    "data": "id,model_version,latency_ms,..."
  }
}
```

### System Monitoring

**GET /metrics** - System metrics
```
Response:
{
  "success": true,
  "data": {
    "cache_stats": {
      "memory_used_human": "2.5M",
      "connected_clients": 5
    }
  }
}
```

**GET /system-status** - System status
```
Response:
{
  "success": true,
  "data": {
    "database": {"status": "healthy"},
    "cache": {"status": "healthy", "enabled": true}
  }
}
```

---

## Database Setup

### Prerequisites

```bash
# Install PostgreSQL
# macOS:
brew install postgresql

# Ubuntu/Debian:
sudo apt-get install postgresql postgresql-contrib

# Windows:
# Download from https://www.postgresql.org/download/windows/
```

### Create Database

```bash
# Start PostgreSQL service
sudo service postgresql start  # Linux
brew services start postgresql  # macOS

# Connect to PostgreSQL
psql -U postgres

# Create database and user
CREATE USER pso_user WITH PASSWORD 'pso_password';
CREATE DATABASE pso_traffic OWNER pso_user;

# Enable required extensions
\connect pso_traffic
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE pso_traffic TO pso_user;

# Exit
\q
```

### Initialize Database Schema

```bash
# Using Flask app initialization (automatic)
python api/app.py

# Or manually with Alembic
cd database/migrations
alembic upgrade head
```

---

## Redis Setup

### Installation

```bash
# macOS:
brew install redis

# Ubuntu/Debian:
sudo apt-get install redis-server

# Windows:
# Use Docker or WSL
docker run -d -p 6379:6379 redis:latest
```

### Start Redis

```bash
# macOS/Linux:
redis-server

# With config file:
redis-server /path/to/redis.conf

# Docker:
docker run -d -p 6379:6379 --name redis redis:latest
```

### Verify Connection

```bash
redis-cli ping
# Should return: PONG
```

---

## Celery Setup

### Installation

Already included in `requirements.txt`. Install with:

```bash
pip install -r requirements.txt
```

### Start Workers

```bash
# Default worker
celery -A workers.celery_app worker --loglevel=info

# Multiple queues
celery -A workers.celery_app worker -Q reports,datasets,models,default

# Beat scheduler (for periodic tasks)
celery -A workers.celery_app beat --loglevel=info

# Combined (development only)
celery -A workers.celery_app worker --beat --loglevel=info
```

### Monitor Celery

```bash
# Install flower (web UI)
pip install flower

# Start flower
celery -A workers.celery_app flower

# Visit: http://localhost:5555
```

---

## Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://pso_user:pso_password@localhost:5432/pso_traffic
SQL_ECHO=false  # Enable SQL logging

# Redis
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Phase 2
PHASE_2_ENABLED=true
```

### Configuration File

Edit `config/config.py`:

```python
# Database
SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://...')
SQLALCHEMY_ECHO = os.getenv('SQL_ECHO', False)

# Redis
REDIS_ENABLED = os.getenv('REDIS_ENABLED', True)
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Celery
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://...')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://...')
```

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup Database

```bash
# Create PostgreSQL database (see section above)
psql -U postgres -c "CREATE DATABASE pso_traffic;"
```

### 3. Setup Redis

```bash
redis-server
```

### 4. Start Application

```bash
python api/app.py
```

### 5. Start Workers (Optional)

```bash
celery -A workers.celery_app worker --beat --loglevel=info
```

### 6. Access System

- Dashboard: http://localhost:5000
- API Docs: http://localhost:5000/docs
- Enterprise API: http://localhost:5000/api/enterprise
- Celery Monitoring: http://localhost:5555 (if Flower installed)

---

## Testing

### Run Tests

```bash
# All tests
pytest tests/ -v

# Specific module
pytest tests/test_auth.py -v

# With coverage
pytest tests/ --cov=api --cov=services --cov=database
```

### Create Test Data

```python
from database import get_db
from database.models import TrafficData, User
from services.storage_service import StorageService

with get_db() as session:
    # Create user
    user = User(email='test@example.com', username='testuser')
    session.add(user)
    session.commit()
    
    # Upload dataset
    dataset = StorageService.upload_dataset(
        session,
        filename='test.csv',
        file_path='/path/to/test.csv',
        uploader_id=user.id,
        row_count=1000,
        column_count=8,
        columns=['time', 'hour', 'density', ...]
    )
```

---

## Performance Optimization

### Database

- Connection pooling enabled (10 active, 20 max)
- Indexes on frequently queried columns
- Query optimization for large datasets
- Lazy loading for relationships

### Caching

- Redis for prediction/optimization results
- Dashboard statistics cached (5 min TTL)
- Analytics data cached (30 min TTL)
- Cache invalidation on data changes

### Background Jobs

- Celery for async operations
- Multiple worker processes
- Task queues for different job types
- Automatic retry with backoff

### Queries

- Pagination for list endpoints (default: 10/50 per page)
- Aggregation queries for analytics
- Index usage for filtering
- Lazy loading to prevent N+1 queries

---

## Security Considerations

- Database credentials in environment variables only
- Redis protected with AUTH (optional)
- Celery task serialization (JSON by default)
- Audit logging for all actions
- RBAC enforced on all endpoints
- Input validation on all API calls
- SQL injection prevention via ORM
- XSS prevention via JSON responses

---

## Troubleshooting

### Database Connection Issues

```
Error: psycopg2.OperationalError: could not connect to server

Solution:
1. Verify PostgreSQL is running: sudo service postgresql status
2. Check DATABASE_URL environment variable
3. Verify database exists: psql -U postgres -l
4. Check credentials are correct
```

### Redis Connection Issues

```
Error: ConnectionError: Error 111 connecting to localhost:6379

Solution:
1. Verify Redis is running: redis-cli ping
2. Check REDIS_URL environment variable
3. Verify Redis port (default 6379)
4. If disabled, set REDIS_ENABLED=false
```

### Celery Worker Issues

```
Error: No module named 'workers'

Solution:
1. Ensure current directory is project root
2. Check PYTHONPATH includes project directory
3. Verify celery_app.py is in workers/
4. Try: export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

---

## Next Steps (Phase 3)

- [ ] GraphQL API layer
- [ ] Real-time WebSocket support
- [ ] Advanced caching strategies
- [ ] Machine learning pipeline
- [ ] Kubernetes deployment
- [ ] Prometheus metrics
- [ ] Distributed tracing
- [ ] API versioning
- [ ] Rate limiting per user
- [ ] Webhook support

---

**Phase 2 Status**: Complete ✅
**Database**: PostgreSQL ✅
**Caching**: Redis ✅
**Background Jobs**: Celery ✅
**Analytics**: Active ✅
**Monitoring**: Ready ✅
**Event System**: Initialized ✅
**Production Ready**: Yes ✅
