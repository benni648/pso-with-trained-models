"""
Model Lifecycle Tasks — Phase 5 (Step 5.4)
===========================================
Automated model retraining via Celery beat:

  - nightly_retrain_task : beat-scheduled (02:00 daily); runs the
    AutoML search and archives the winning model + report.
  - retrain_model_task   : on-demand variant (used by the API's
    POST /api/models/retrain endpoint).

Both are safe to run without Redis/Celery — the API layer falls back
to a synchronous call when the broker is unavailable.
"""

from workers.celery_app import app
from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


def _run_retrain(quick: bool) -> dict:
    """Shared retrain implementation (synchronous)."""
    from intelligence.automl import run_automl, REPORT_PATH, BEST_MODEL_PATH
    import json
    import os

    report = run_automl(quick=quick)

    result = {
        "best_model": report.get("best_model"),
        "results": report.get("results"),
        "report_path": REPORT_PATH,
        "model_path": BEST_MODEL_PATH,
        "elapsed_s": report.get("elapsed_s"),
    }
    logger.info(
        "Retraining complete: winner=%s (R2=%s)",
        report.get("best_model", {}).get("name"),
        report.get("best_model", {}).get("avg_r2"),
    )
    return result


@app.task(
    name="workers.tasks.model_tasks.retrain_model_task",
    bind=True,
    max_retries=1,
)
def retrain_model_task(self, quick: bool = False) -> dict:
    """On-demand AutoML retraining task."""
    try:
        return _run_retrain(quick)
    except Exception as exc:
        logger.exception(f"Retrain task failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@app.task(name="workers.tasks.model_tasks.nightly_retrain_task")
def nightly_retrain_task() -> dict:
    """
    Nightly full AutoML retraining (beat schedule: 02:00 daily).

    Keeps saved_models/automl_report.json and automl_best_model.pkl
    fresh so operators always have a recent model comparison.
    """
    try:
        return _run_retrain(quick=False)
    except Exception as exc:
        logger.exception(f"Nightly retrain failed: {exc}")
        return {"error": str(exc)}
