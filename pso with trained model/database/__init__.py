"""
Database module initialization.

Provides database connection, session management, and model access.
"""

from database.database import (
    init_db,
    get_session,
    get_db,
    Base,
    engine
)

from database.models import (
    User,
    TrafficData,
    Prediction,
    Optimization,
    Report,
    AuditLog,
    ModelRegistry,
)

__all__ = [
    'init_db',
    'get_session',
    'get_db',
    'Base',
    'engine',
    'User',
    'TrafficData',
    'Prediction',
    'Optimization',
    'Report',
    'AuditLog',
    'ModelRegistry',
]
