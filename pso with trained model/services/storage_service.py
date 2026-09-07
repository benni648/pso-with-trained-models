"""
Storage Service — dataset upload and management.

Features:
  - SHA256 file deduplication
  - Metadata tracking
  - Pagination support
"""

import hashlib
from datetime import datetime
from typing import Tuple, List, Optional, Any

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


class StorageService:
    """
    Manages traffic dataset storage and retrieval.

    Usage:
        with get_db() as session:
            datasets, total = StorageService.get_datasets(session, limit=10, offset=0)
    """

    @staticmethod
    def get_datasets(
        session,
        limit: int = 10,
        offset: int = 0,
    ) -> Tuple[List, int]:
        """
        Get paginated list of datasets.

        Returns
        -------
        tuple
            (list of datasets, total count)
        """
        from database.models import TrafficData

        query = session.query(TrafficData).order_by(TrafficData.uploaded_at.desc())
        total = query.count()
        datasets = query.limit(limit).offset(offset).all()

        return datasets, total

    @staticmethod
    def get_dataset_statistics(session, dataset_id: int) -> Optional[Any]:
        """
        Get detailed statistics for a specific dataset.

        Returns
        -------
        dict or None
            Dataset statistics, or None if not found.
        """
        from database.models import TrafficData

        dataset = session.query(TrafficData).filter_by(id=dataset_id).first()
        if not dataset:
            return None

        return {
            "id": dataset.id,
            "filename": dataset.filename,
            "row_count": dataset.row_count,
            "column_count": dataset.column_count,
            "file_size": dataset.file_size,
            "columns": dataset.columns,
            "status": dataset.status,
            "statistics": dataset.statistics,
            "uploaded_at": dataset.uploaded_at.isoformat() if dataset.uploaded_at else None,
            "data_hash": dataset.data_hash,
        }

    @staticmethod
    def delete_dataset(session, dataset_id: int) -> bool:
        """
        Delete a dataset by ID.

        Returns
        -------
        bool
            True if deleted, False if not found.
        """
        from database.models import TrafficData

        dataset = session.query(TrafficData).filter_by(id=dataset_id).first()
        if not dataset:
            return False

        session.delete(dataset)
        session.commit()

        logger.info(f"Dataset deleted: {dataset_id} ({dataset.filename})")
        return True

    @staticmethod
    def compute_file_hash(file_content: bytes) -> str:
        """Compute SHA256 hash of file content."""
        return hashlib.sha256(file_content).hexdigest()
