"""Initial schema creation - Create all tables.

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all initial tables."""
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=False),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username'),
    )
    op.create_index('ix_users_email_active', 'users', ['email', 'is_active'])
    op.create_index('ix_users_role', 'users', ['role'])
    op.create_index('ix_users_email', 'users', ['email'])
    
    # Create traffic_data table
    op.create_table(
        'traffic_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('uploader_id', sa.Integer(), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False),
        sa.Column('column_count', sa.Integer(), nullable=False),
        sa.Column('columns', postgresql.JSON(), nullable=True),
        sa.Column('date_range_start', sa.DateTime(), nullable=True),
        sa.Column('date_range_end', sa.DateTime(), nullable=True),
        sa.Column('data_hash', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.Column('statistics', postgresql.JSON(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['uploader_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('data_hash'),
    )
    op.create_index('ix_traffic_data_uploader_uploaded', 'traffic_data', ['uploader_id', 'uploaded_at'])
    op.create_index('ix_traffic_data_status', 'traffic_data', ['status'])
    op.create_index('ix_traffic_data_id', 'traffic_data', ['id'])
    
    # Create model_registry table
    op.create_table(
        'model_registry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('model_type', sa.String(length=100), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('training_dataset', sa.String(length=255), nullable=True),
        sa.Column('training_date', sa.DateTime(), nullable=False),
        sa.Column('training_parameters', postgresql.JSON(), nullable=True),
        sa.Column('metrics', postgresql.JSON(), nullable=True),
        sa.Column('validation_score', sa.DECIMAL(precision=10, scale=6), nullable=True),
        sa.Column('test_score', sa.DECIMAL(precision=10, scale=6), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('is_production', sa.Boolean(), nullable=False),
        sa.Column('is_current', sa.Boolean(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('changelog', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('activated_at', sa.DateTime(), nullable=True),
        sa.Column('deactivated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'version', name='uq_model_name_version'),
    )
    op.create_index('ix_model_status', 'model_registry', ['status'])
    op.create_index('ix_model_is_current', 'model_registry', ['is_current'])
    op.create_index('ix_model_is_production', 'model_registry', ['is_production'])
    
    # Create predictions table
    op.create_table(
        'predictions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=True),
        sa.Column('traffic_data_id', sa.Integer(), nullable=True),
        sa.Column('time_step', sa.Integer(), nullable=False),
        sa.Column('hour', sa.Integer(), nullable=False),
        sa.Column('density', sa.DECIMAL(precision=10, scale=6), nullable=False),
        sa.Column('avg_wait_time', sa.DECIMAL(precision=10, scale=6), nullable=False),
        sa.Column('congestion_level', sa.String(length=50), nullable=False),
        sa.Column('input_features', postgresql.JSON(), nullable=False),
        sa.Column('predicted_vehicles', postgresql.JSON(), nullable=False),
        sa.Column('confidence_scores', postgresql.JSON(), nullable=True),
        sa.Column('latency_ms', sa.DECIMAL(precision=10, scale=3), nullable=False),
        sa.Column('model_version', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('request_id', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['model_registry.id'], ),
        sa.ForeignKeyConstraint(['traffic_data_id'], ['traffic_data.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('request_id'),
    )
    op.create_index('ix_predictions_user_created', 'predictions', ['user_id', 'created_at'])
    op.create_index('ix_predictions_created', 'predictions', ['created_at'])
    op.create_index('ix_predictions_status', 'predictions', ['status'])
    
    # Create optimizations table
    op.create_table(
        'optimizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('prediction_id', sa.Integer(), nullable=True),
        sa.Column('predicted_vehicles', postgresql.JSON(), nullable=False),
        sa.Column('initial_signal_timings', postgresql.JSON(), nullable=True),
        sa.Column('n_particles', sa.Integer(), nullable=False),
        sa.Column('n_iterations', sa.Integer(), nullable=False),
        sa.Column('inertia_weight', sa.DECIMAL(precision=10, scale=6), nullable=True),
        sa.Column('cognitive_coefficient', sa.DECIMAL(precision=10, scale=6), nullable=True),
        sa.Column('social_coefficient', sa.DECIMAL(precision=10, scale=6), nullable=True),
        sa.Column('optimized_signal_timings', postgresql.JSON(), nullable=False),
        sa.Column('fitness_score', sa.DECIMAL(precision=15, scale=8), nullable=False),
        sa.Column('best_fitness', sa.DECIMAL(precision=15, scale=8), nullable=True),
        sa.Column('average_fitness', sa.DECIMAL(precision=15, scale=8), nullable=True),
        sa.Column('duration_ms', sa.DECIMAL(precision=10, scale=3), nullable=False),
        sa.Column('iterations_completed', sa.Integer(), nullable=True),
        sa.Column('convergence_iteration', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('algorithm_version', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['prediction_id'], ['predictions.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_optimizations_user_created', 'optimizations', ['user_id', 'created_at'])
    op.create_index('ix_optimizations_created', 'optimizations', ['created_at'])
    op.create_index('ix_optimizations_fitness', 'optimizations', ['fitness_score'])
    
    # Create reports table
    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('format', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('prediction_ids', postgresql.JSON(), nullable=True),
        sa.Column('optimization_ids', postgresql.JSON(), nullable=True),
        sa.Column('statistics', postgresql.JSON(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.Column('accessed_at', sa.DateTime(), nullable=True),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.Column('period_start', sa.DateTime(), nullable=True),
        sa.Column('period_end', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_reports_user_generated', 'reports', ['user_id', 'generated_at'])
    op.create_index('ix_reports_generated', 'reports', ['generated_at'])
    
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=100), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('request_id', sa.String(length=100), nullable=True),
        sa.Column('old_values', postgresql.JSON(), nullable=True),
        sa.Column('new_values', postgresql.JSON(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_logs_user_created', 'audit_logs', ['user_id', 'created_at'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_created', 'audit_logs', ['created_at'])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_index('ix_audit_logs_created', table_name='audit_logs')
    op.drop_index('ix_audit_logs_action', table_name='audit_logs')
    op.drop_index('ix_audit_logs_user_created', table_name='audit_logs')
    op.drop_table('audit_logs')
    
    op.drop_index('ix_reports_generated', table_name='reports')
    op.drop_index('ix_reports_user_generated', table_name='reports')
    op.drop_table('reports')
    
    op.drop_index('ix_optimizations_fitness', table_name='optimizations')
    op.drop_index('ix_optimizations_created', table_name='optimizations')
    op.drop_index('ix_optimizations_user_created', table_name='optimizations')
    op.drop_table('optimizations')
    
    op.drop_index('ix_predictions_status', table_name='predictions')
    op.drop_index('ix_predictions_created', table_name='predictions')
    op.drop_index('ix_predictions_user_created', table_name='predictions')
    op.drop_table('predictions')
    
    op.drop_index('ix_model_is_production', table_name='model_registry')
    op.drop_index('ix_model_is_current', table_name='model_registry')
    op.drop_index('ix_model_status', table_name='model_registry')
    op.drop_table('model_registry')
    
    op.drop_index('ix_traffic_data_id', table_name='traffic_data')
    op.drop_index('ix_traffic_data_status', table_name='traffic_data')
    op.drop_index('ix_traffic_data_uploader_uploaded', table_name='traffic_data')
    op.drop_table('traffic_data')
    
    op.drop_index('ix_users_role', table_name='users')
    op.drop_index('ix_users_email_active', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
