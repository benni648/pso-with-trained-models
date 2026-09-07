"""
Dataset Tasks — background dataset processing and validation.

These tasks run asynchronously via Celery workers.
"""

from datetime import datetime, timedelta

from workers.celery_app import app
from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


@app.task(name="workers.tasks.dataset_tasks.process_dataset_task", bind=True, max_retries=3)
def process_dataset_task(self, dataset_id: int):
    """
    Process an uploaded dataset in the background.

    Parameters
    ----------
    dataset_id : int
        ID of the dataset to process.
    """
    try:
        from database import get_db
        from database.models import TrafficData

        with get_db() as session:
            dataset = session.query(TrafficData).filter_by(id=dataset_id).first()
            if not dataset:
                logger.warning(f"Dataset {dataset_id} not found")
                return {"status": "not_found"}

            # Update status
            dataset.status = "PROCESSING"
            session.commit()

            # TODO: Add actual processing logic here
            # - Validate columns
            # - Compute statistics
            # - Generate data quality report

            # Mark as processed
            dataset.status = "PROCESSED"
            dataset.processed_at = datetime.utcnow()
            session.commit()

            logger.info(f"Dataset {dataset_id} processed successfully")
            return {"status": "completed", "dataset_id": dataset_id}

    except Exception as exc:
        logger.error(f"Dataset processing failed: {str(exc)}")
        self.retry(exc=exc, countdown=60)


@app.task(name="workers.tasks.dataset_tasks.archive_old_datasets")
def archive_old_datasets(days: int = 180):
    """
    Archive datasets older than N days.

    Parameters
    ----------
    days : int
        Archive datasets older than this many days.
    """
    try:
        from database import get_db
        from database.models import TrafficData

        cutoff = datetime.utcnow() - timedelta(days=days)

        with get_db() as session:
            old_datasets = session.query(TrafficData).filter(
                TrafficData.uploaded_at < cutoff,
                TrafficData.status != "ARCHIVED"
            ).all()

            for dataset in old_datasets:
                dataset.status = "ARCHIVED"
                dataset.archived_at = datetime.utcnow()

            session.commit()

            logger.info(f"Archived {len(old_datasets)} old datasets")
            return {"archived": len(old_datasets)}

    except Exception as e:
        logger.error(f"Dataset archival failed: {str(e)}")
        return {"archived": 0, "error": str(e)}
