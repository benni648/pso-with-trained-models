"""
SQLAlchemy ORM models for the PSO Traffic System.

Models:
- User: System users with roles
- TrafficData: Uploaded traffic datasets
- Prediction: ML prediction records
- Optimization: PSO optimization records
- Report: Generated reports
- AuditLog: Action audit trail
- ModelRegistry: ML model versioning
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text, 
    JSON, ForeignKey, Enum, Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.types import DECIMAL
import enum

from database.database import Base


class User(Base):
    """User model for authentication and authorization."""
    
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default='VIEWER')  # ADMIN, TRAFFIC_OPERATOR, VIEWER
    is_active = Column(Boolean, default=True, index=True)
    is_admin = Column(Boolean, default=False)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    traffic_data = relationship('TrafficData', back_populates='uploader')
    predictions = relationship('Prediction', back_populates='user')
    optimizations = relationship('Optimization', back_populates='user')
    audit_logs = relationship('AuditLog', back_populates='user')
    
    __table_args__ = (
        Index('ix_users_email_active', 'email', 'is_active'),
        Index('ix_users_role', 'role'),
    )


class TrafficData(Base):
    """Traffic dataset storage."""
    
    __tablename__ = 'traffic_data'
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=False)
    uploader_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    # Metadata
    row_count = Column(Integer, nullable=False)
    column_count = Column(Integer, nullable=False)
    columns = Column(JSON, nullable=True)  # List of column names
    date_range_start = Column(DateTime, nullable=True)
    date_range_end = Column(DateTime, nullable=True)
    data_hash = Column(String(64), unique=True, nullable=True)  # SHA256 for deduplication
    
    # Status and timestamps
    status = Column(String(50), default='STORED')  # STORED, PROCESSING, PROCESSED, ARCHIVED
    uploaded_at = Column(DateTime, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime, nullable=True)
    archived_at = Column(DateTime, nullable=True)
    
    # Statistics
    statistics = Column(JSON, nullable=True)  # Min, max, mean, std for numeric columns
    description = Column(Text, nullable=True)
    
    # Relationships
    uploader = relationship('User', back_populates='traffic_data')
    predictions = relationship('Prediction', back_populates='traffic_data')
    
    __table_args__ = (
        Index('ix_traffic_data_uploader_uploaded', 'uploader_id', 'uploaded_at'),
        Index('ix_traffic_data_status', 'status'),
    )


class Prediction(Base):
    """ML prediction history."""
    
    __tablename__ = 'predictions'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    model_id = Column(Integer, ForeignKey('model_registry.id'), nullable=True)
    traffic_data_id = Column(Integer, ForeignKey('traffic_data.id'), nullable=True)
    
    # Input data
    time_step = Column(Integer, nullable=False)
    hour = Column(Integer, nullable=False)
    density = Column(DECIMAL(10, 6), nullable=False)
    avg_wait_time = Column(DECIMAL(10, 6), nullable=False)
    congestion_level = Column(String(50), nullable=False)
    input_features = Column(JSON, nullable=False)  # Full input data
    
    # Output data
    predicted_vehicles = Column(JSON, nullable=False)  # Predictions for each direction
    confidence_scores = Column(JSON, nullable=True)
    
    # Performance metrics
    latency_ms = Column(DECIMAL(10, 3), nullable=False)
    model_version = Column(String(100), nullable=True)
    
    # Status and timestamps
    status = Column(String(50), default='SUCCESSFUL')  # SUCCESSFUL, FAILED, CANCELLED
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Metadata
    request_id = Column(String(100), unique=True, nullable=True)
    
    # Relationships
    user = relationship('User', back_populates='predictions')
    traffic_data = relationship('TrafficData', back_populates='predictions')
    model = relationship('ModelRegistry', back_populates='predictions')
    
    __table_args__ = (
        Index('ix_predictions_user_created', 'user_id', 'created_at'),
        Index('ix_predictions_created', 'created_at'),
        Index('ix_predictions_status', 'status'),
    )


class Optimization(Base):
    """PSO optimization execution history."""
    
    __tablename__ = 'optimizations'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    prediction_id = Column(Integer, ForeignKey('predictions.id'), nullable=True)
    
    # Input data
    predicted_vehicles = Column(JSON, nullable=False)
    initial_signal_timings = Column(JSON, nullable=True)
    
    # PSO Parameters
    n_particles = Column(Integer, nullable=False)
    n_iterations = Column(Integer, nullable=False)
    inertia_weight = Column(DECIMAL(10, 6), nullable=True)
    cognitive_coefficient = Column(DECIMAL(10, 6), nullable=True)
    social_coefficient = Column(DECIMAL(10, 6), nullable=True)
    
    # Results
    optimized_signal_timings = Column(JSON, nullable=False)
    fitness_score = Column(DECIMAL(15, 8), nullable=False)
    best_fitness = Column(DECIMAL(15, 8), nullable=True)
    average_fitness = Column(DECIMAL(15, 8), nullable=True)
    
    # Performance metrics
    duration_ms = Column(DECIMAL(10, 3), nullable=False)
    iterations_completed = Column(Integer, nullable=True)
    convergence_iteration = Column(Integer, nullable=True)
    
    # Status and timestamps
    status = Column(String(50), default='SUCCESSFUL')  # SUCCESSFUL, FAILED, TIMEOUT
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Metadata
    algorithm_version = Column(String(100), nullable=True)
    
    # Relationships
    user = relationship('User', back_populates='optimizations')
    
    __table_args__ = (
        Index('ix_optimizations_user_created', 'user_id', 'created_at'),
        Index('ix_optimizations_created', 'created_at'),
        Index('ix_optimizations_fitness', 'fitness_score'),
    )


class Report(Base):
    """Generated reports."""
    
    __tablename__ = 'reports'
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    
    # Report content
    format = Column(String(20), nullable=False)  # JSON, CSV, PDF, XLSX
    content = Column(Text, nullable=True)  # For text formats
    file_path = Column(String(500), nullable=True)  # For binary formats
    file_size = Column(Integer, nullable=True)
    
    # Data references
    prediction_ids = Column(JSON, nullable=True)
    optimization_ids = Column(JSON, nullable=True)
    
    # Statistics
    statistics = Column(JSON, nullable=True)
    
    # Status and timestamps
    status = Column(String(50), default='GENERATED')  # GENERATED, EMAILED, ARCHIVED
    generated_at = Column(DateTime, default=datetime.utcnow, index=True)
    accessed_at = Column(DateTime, nullable=True)
    archived_at = Column(DateTime, nullable=True)
    
    # Period covered
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('ix_reports_user_generated', 'user_id', 'generated_at'),
        Index('ix_reports_generated', 'generated_at'),
    )


class AuditLog(Base):
    """Action audit trail."""
    
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    # Action details
    action = Column(String(100), nullable=False)  # LOGIN, UPLOAD, PREDICT, OPTIMIZE, DOWNLOAD, DELETE
    resource_type = Column(String(100), nullable=False)  # User, Dataset, Prediction, etc
    resource_id = Column(Integer, nullable=True)
    
    # Request information
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(String(500), nullable=True)
    request_id = Column(String(100), nullable=True)
    
    # Changes
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    
    # Status
    status = Column(String(50), nullable=False)  # SUCCESS, FAILURE
    error_message = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship('User', back_populates='audit_logs')
    
    __table_args__ = (
        Index('ix_audit_logs_user_created', 'user_id', 'created_at'),
        Index('ix_audit_logs_action', 'action'),
        Index('ix_audit_logs_created', 'created_at'),
    )


class ModelRegistry(Base):
    """ML model versioning and registry."""
    
    __tablename__ = 'model_registry'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    version = Column(String(50), nullable=False)
    model_type = Column(String(100), nullable=False)  # RANDOM_FOREST, XGBoost, Neural_Network
    
    # File information
    file_path = Column(String(500), nullable=False)
    file_hash = Column(String(64), nullable=True)  # SHA256
    file_size = Column(Integer, nullable=True)
    
    # Training information
    training_dataset = Column(String(255), nullable=True)
    training_date = Column(DateTime, nullable=False)
    training_parameters = Column(JSON, nullable=True)
    
    # Performance metrics
    metrics = Column(JSON, nullable=True)  # Accuracy, precision, recall, F1, etc
    validation_score = Column(DECIMAL(10, 6), nullable=True)
    test_score = Column(DECIMAL(10, 6), nullable=True)
    
    # Status
    status = Column(String(50), default='ACTIVE')  # ACTIVE, INACTIVE, ARCHIVED, DEPRECATED
    is_production = Column(Boolean, default=False)
    is_current = Column(Boolean, default=False)
    
    # Metadata
    description = Column(Text, nullable=True)
    changelog = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    activated_at = Column(DateTime, nullable=True)
    deactivated_at = Column(DateTime, nullable=True)
    
    # Relationships
    predictions = relationship('Prediction', back_populates='model')
    
    __table_args__ = (
        UniqueConstraint('name', 'version', name='uq_model_name_version'),
        Index('ix_model_status', 'status'),
        Index('ix_model_is_current', 'is_current'),
        Index('ix_model_is_production', 'is_production'),
    )


# Create indexes after all models are defined
def create_indexes():
    """Ensure all indexes are created."""
    Base.metadata.create_all()
