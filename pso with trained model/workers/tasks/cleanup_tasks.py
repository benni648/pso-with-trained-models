"""
Cleanup Tasks — background maintenance and health monitoring.

These tasks run asynchronously via Celery workers (or the beat scheduler)
to keep the system healthy: pruning old records, removing temp files,
and reporting system health.
"""

import os
import tempfile
from datetime import datetime, timedelta

from workers.celery_app import app
from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


@app.task(name="workers.tasks.cleanup_tasks.clean_old_audit_logs")
def clean_old_audit_logs(days: int = 365):
    """
    Delete audit logs older than N days.

    Parameters
    ----------
    days : int
        Delete logs older than this many days.
    """
    try:
        from database import get_db
        from database.models import AuditLog

        cutoff = datetime.utcnow() - timedelta(days=days)

        with get_db() as session:
            deleted = session.query(AuditLog).filter(
                AuditLog.created_at < cutoff
            ).delete(synchronize_session=False)
            session.commit()

            logger.info(f"Deleted {deleted} audit logs older than {days} days")
            return {"deleted": deleted}

    except Exception as e:
        logger.error(f"Audit log cleanup failed: {str(e)}")
        return {"deleted": 0, "error": str(e)}


@app.task(name="workers.tasks.cleanup_tasks.clean_old_predictions")
def clean_old_predictions(days: int = 90):
    """
    Delete prediction records older than N days.

    Parameters
    ----------
    days : int
        Delete predictions older than this many days.
    """
    try:
        from database import get_db
        from database.models import Prediction

        cutoff = datetime.utcnow() - timedelta(days=days)

        with get_db() as session:
            deleted = session.query(Prediction).filter(
                Prediction.created_at < cutoff
            ).delete(synchronize_session=False)
            session.commit()

            logger.info(f"Deleted {deleted} predictions older than {days} days")
            return {"deleted": deleted}

    except Exception as e:
        logger.error(f"Prediction cleanup failed: {str(e)}")
        return {"deleted": 0, "error": str(e)}


@app.task(name="workers.tasks.cleanup_tasks.clean_temp_files")
def clean_temp_files(days: int = 7):
    """
    Remove temp files older than N days.

    Parameters
    ----------
    days : int
        Remove files older than this many days.
    """
    try:
        cutoff = datetime.now() - timedelta(days=days)
        removed = 0

        temp_dir = tempfile.gettempdir()
        for filename in os.listdir(temp_dir):
            filepath = os.path.join(temp_dir, filename)
            try:
                if os.path.isfile(filepath):
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if mtime < cutoff:
                        os.remove(filepath)
                        removed += 1
            except (OSError, PermissionError):
                continue

        logger.info(f"Removed {removed} temp files older than {days} days")
        return {"removed": removed}

    except Exception as e:
        logger.error(f"Temp file cleanup failed: {str(e)}")
        return {"removed": 0, "error": str(e)}


@app.task(name="workers.tasks.cleanup_tasks.health_check")
def health_check():
    """
    Periodic health check task (runs via Celery beat every 5 minutes).

    Reports system health so operators can monitor the worker's view
    of the running services.
    """
    try:
        import psutil

        memory = psutil.virtual_memory()
        health = {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "UP",
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_used_percent": memory.percent,
            "disk_free_gb": round(psutil.disk_usage("/").free / (1024 ** 3), 2),
        }

        # Include model availability
        try:
            from config.config import config
            model_path = os.path.join(config.MODEL_DIR, config.ML_MODEL_NAME)
            health["model_loaded"] = os.path.exists(model_path)
        except (ImportError, AttributeError):
            health["model_loaded"] = None

        logger.info(f"Health check: {health['status']} | CPU {health['cpu_percent']}% | MEM {health['memory_used_percent']}%")
        return health

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {"status": "DOWN", "error": str(e)}