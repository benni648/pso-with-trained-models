"""
Report Tasks — background report generation and archiving.

These tasks run asynchronously via Celery workers.
"""

import os
from datetime import datetime, timedelta

from workers.celery_app import app
from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


@app.task(name="workers.tasks.report_tasks.generate_report_task", bind=True, max_retries=3)
def generate_report_task(self, report_config: dict):
    """
    Generate a traffic report in the background.

    Parameters
    ----------
    report_config : dict
        Report configuration: {title, format, prediction_ids, optimization_ids}
    """
    try:
        from services.report_service import ReportGenerator

        generator = ReportGenerator()
        title = report_config.get("title", "Background Report")
        format_type = report_config.get("format", "json")

        filepath = generator.generate_traffic_report(
            title=title,
            format=format_type,
        )

        logger.info(f"Background report generated: {filepath}")
        return {"status": "completed", "filepath": filepath}

    except Exception as exc:
        logger.error(f"Report generation failed: {str(exc)}")
        self.retry(exc=exc, countdown=60)


@app.task(name="workers.tasks.report_tasks.archive_old_reports")
def archive_old_reports(days: int = 90):
    """
    Archive reports older than N days.

    Parameters
    ----------
    days : int
        Archive reports older than this many days.
    """
    try:
        from config.config import config
        reports_dir = config.REPORTS_DIR
    except (ImportError, AttributeError):
        reports_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "reports"
        )

    cutoff = datetime.utcnow() - timedelta(days=days)
    archived = 0

    if not os.path.exists(reports_dir):
        return {"archived": 0}

    for filename in os.listdir(reports_dir):
        filepath = os.path.join(reports_dir, filename)
        if os.path.isfile(filepath):
            mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            if mtime < cutoff:
                # Move to archive subdirectory
                archive_dir = os.path.join(reports_dir, "archive")
                os.makedirs(archive_dir, exist_ok=True)
                os.rename(filepath, os.path.join(archive_dir, filename))
                archived += 1

    logger.info(f"Archived {archived} old reports")
    return {"archived": archived}
