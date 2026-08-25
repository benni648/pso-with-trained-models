"""
Database connection and session management.

Provides:
- SQLAlchemy engine and session factory
- Connection pooling
- Transaction management
- Context managers for database access
"""

import os
from contextlib import contextmanager
from sqlalchemy import create_engine, event, pool
from sqlalchemy.orm import sessionmaker, scoped_session, Session
from sqlalchemy.ext.declarative import declarative_base

# Get database URL from environment or use default
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://pso_user:pso_password@localhost:5432/pso_traffic'
)

# Create declarative base for all models
Base = declarative_base()

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=pool.QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,   # Recycle connections after 1 hour
    echo=os.getenv('SQL_ECHO', 'false').lower() == 'true',  # SQL logging
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

# Create scoped session for thread-safe access
ScopedSession = scoped_session(SessionLocal)


def init_db():
    """Initialize database - create all tables."""
    Base.metadata.create_all(bind=engine)
    print("✓ Database initialized successfully")


def get_session() -> Session:
    """Get a new database session."""
    return SessionLocal()


@contextmanager
def get_db():
    """
    Context manager for database sessions.
    
    Usage:
        with get_db() as session:
            user = session.query(User).first()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def close_db():
    """Close database connection."""
    ScopedSession.remove()
    engine.dispose()


# Event listeners for connection management
@event.listens_for(engine, 'connect')
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable foreign keys for SQLite connections."""
    # This is useful for testing with SQLite
    if hasattr(dbapi_conn, 'execute'):
        try:
            dbapi_conn.execute('PRAGMA foreign_keys=ON')
        except Exception:
            pass


# Health check function for monitoring
def check_db_connection():
    """Check if database connection is working."""
    try:
        with get_db() as session:
            session.execute('SELECT 1')
        return True, "Database connection OK"
    except Exception as e:
        return False, f"Database connection failed: {str(e)}"


def get_connection_pool_status():
    """Get connection pool statistics."""
    if hasattr(engine.pool, 'size'):
        return {
            'pool_size': engine.pool.size(),
            'checked_in_connections': engine.pool.checkedin(),
            'checked_out_connections': engine.pool.checkedout(),
            'overflow_created': engine.pool.overflow(),
            'total_connections': engine.pool.size() + engine.pool.overflow(),
        }
    return {}
