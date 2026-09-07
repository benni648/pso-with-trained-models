"""
Audit Service — tracks all user actions for compliance and debugging.

Logs every significant action: login, predict, optimize, delete, etc.
"""

from datetime import datetime
from typing import Tuple, List, Optional

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


class AuditService:
    """
    Logs and queries user actions in the audit trail.

    Usage:
        AuditService.log_action(session, user_id=1, action="LOGIN", resource_type="User")
    """

    @staticmethod
    def log_action(
        session,
        user_id: int,
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        status: str = "SUCCESS",
    ):
        """
        Log a user action.

        Parameters
        ----------
        session : Session
            Database session.
        user_id : int
            ID of the user performing the action.
        action : str
            Action type (e.g., LOGIN, PREDICTION_REQUEST, OPTIMIZATION_REQUEST).
        resource_type : str
            Type of resource affected (e.g., User, Prediction, Dataset).
        resource_id : int, optional
            ID of the affected resource.
        old_values : dict, optional
            Previous values (for updates).
        new_values : dict, optional
            New values (for updates).
        status : str
            Action status: SUCCESS or FAILURE.
        """
        from database.models import AuditLog

        try:
            log_entry = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                old_values=old_values,
                new_values=new_values,
                status=status,
                created_at=datetime.utcnow(),
            )
            session.add(log_entry)
            session.commit()

            logger.debug(f"Audit: {action} on {resource_type}:{resource_id} by user:{user_id}")

        except Exception as e:
            logger.error(f"Failed to write audit log: {str(e)}")
            session.rollback()

    @staticmethod
    def get_action_audit_logs(
        session,
        action: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List, int]:
        """
        Get audit logs filtered by action type.

        Returns
        -------
        tuple
            (list of log entries, total count)
        """
        from database.models import AuditLog

        query = session.query(AuditLog).filter_by(action=action)
        total = query.count()
        logs = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset).all()

        return logs, total
