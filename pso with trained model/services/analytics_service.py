"""
Analytics Service — business intelligence and trend analysis.

Provides overview stats, performance metrics, and historical trends.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


class AnalyticsService:
    """
    Provides analytics and business intelligence.

    Usage:
        with get_db() as session:
            stats = AnalyticsService.get_overview_stats(session)
    """

    @staticmethod
    def get_overview_stats(session, days: int = 7) -> Dict[str, Any]:
        """
        Get high-level overview statistics.

        Parameters
        ----------
        session : Session
            Database session.
        days : int
            Number of days to look back.

        Returns
        -------
        dict
            Overview metrics.
        """
        from database.models import Prediction, Optimization, TrafficData
        from sqlalchemy import func

        start_date = datetime.utcnow() - timedelta(days=days)

        total_predictions = session.query(Prediction).filter(
            Prediction.created_at >= start_date
        ).count()

        successful_predictions = session.query(Prediction).filter(
            Prediction.created_at >= start_date,
            Prediction.status == "SUCCESSFUL"
        ).count()

        total_optimizations = session.query(Optimization).filter(
            Optimization.created_at >= start_date
        ).count()

        avg_latency = session.query(func.avg(Prediction.latency_ms)).filter(
            Prediction.created_at >= start_date,
            Prediction.status == "SUCCESSFUL"
        ).scalar()

        avg_fitness = session.query(func.avg(Optimization.fitness_score)).filter(
            Optimization.created_at >= start_date,
            Optimization.status == "SUCCESSFUL"
        ).scalar()

        datasets_count = session.query(TrafficData).count()

        return {
            "period_days": days,
            "total_predictions": total_predictions,
            "successful_predictions": successful_predictions,
            "total_optimizations": total_optimizations,
            "average_prediction_latency_ms": round(float(avg_latency), 2) if avg_latency else 0,
            "average_fitness_score": round(float(avg_fitness), 4) if avg_fitness else 0,
            "datasets_uploaded": datasets_count,
        }

    @staticmethod
    def get_performance_metrics(session) -> Dict[str, Any]:
        """Get system performance metrics."""
        from database.models import Prediction, Optimization
        from sqlalchemy import func

        total_pred = session.query(Prediction).count()
        success_pred = session.query(Prediction).filter_by(status="SUCCESSFUL").count()

        total_opt = session.query(Optimization).count()
        success_opt = session.query(Optimization).filter_by(status="SUCCESSFUL").count()

        best_fitness = session.query(func.max(Optimization.fitness_score)).filter(
            Optimization.status == "SUCCESSFUL"
        ).scalar()

        return {
            "prediction_success_rate": round(success_pred / total_pred * 100, 1) if total_pred > 0 else 0,
            "optimization_success_rate": round(success_opt / total_opt * 100, 1) if total_opt > 0 else 0,
            "total_predictions": total_pred,
            "total_optimizations": total_opt,
            "best_fitness_score": round(float(best_fitness), 4) if best_fitness else 0,
        }

    @staticmethod
    def get_trend_analysis(session, days: int = 30) -> Dict[str, Any]:
        """Get trend data over time."""
        from database.models import Prediction, Optimization

        start_date = datetime.utcnow() - timedelta(days=days)
        trends = []

        for i in range(days):
            day = start_date + timedelta(days=i)
            next_day = day + timedelta(days=1)

            pred_count = session.query(Prediction).filter(
                Prediction.created_at >= day,
                Prediction.created_at < next_day
            ).count()

            opt_count = session.query(Optimization).filter(
                Optimization.created_at >= day,
                Optimization.created_at < next_day
            ).count()

            trends.append({
                "date": day.strftime("%Y-%m-%d"),
                "predictions": pred_count,
                "optimizations": opt_count,
            })

        return {
            "period_days": days,
            "trends": trends,
        }
