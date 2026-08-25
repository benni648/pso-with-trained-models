"""
Phase 2 Enterprise API Routes

Adds:
- Dataset management
- Prediction history
- Optimization history
- Analytics
- Audit logs
- Monitoring
- Model registry
- Data export
- System status
"""

from flask import request, jsonify, Blueprint
from datetime import datetime, timedelta
from utils.response import APIResponse
from utils.errors import TrafficAPIError, InternalServerError
from utils.auth import RoleManager
from utils.logger import LoggerManager
from services.storage_service import StorageService
from services.audit_service import AuditService
from services.analytics_service import AnalyticsService
from services.cache_service import CacheService
from database import get_session, get_db
from database.models import (
    TrafficData, Prediction, Optimization, Report, 
    AuditLog, ModelRegistry, User
)
from events import EventBus, DatasetUploadedEvent, PredictionCreatedEvent
from workers.tasks.report_tasks import generate_report_task

logger = LoggerManager.get_logger(__name__)

# Create Blueprint
enterprise_bp = Blueprint('enterprise', __name__, url_prefix='/api/enterprise')


# ========================
# Dataset Management
# ========================

@enterprise_bp.route('/datasets', methods=['GET'])
@RoleManager.require_permission('predict')
def get_datasets():
    """Get list of uploaded datasets."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        offset = (page - 1) * per_page
        
        with get_db() as session:
            datasets, total = StorageService.get_datasets(
                session,
                limit=per_page,
                offset=offset
            )
            
            data = [{
                'id': d.id,
                'filename': d.filename,
                'row_count': d.row_count,
                'column_count': d.column_count,
                'file_size': d.file_size,
                'status': d.status,
                'uploaded_at': d.uploaded_at.isoformat(),
                'uploader_id': d.uploader_id
            } for d in datasets]
            
            return APIResponse.paginated(data, total, page, per_page)
    except Exception as e:
        logger.error(f"Error fetching datasets: {str(e)}")
        return APIResponse.error('FETCH_ERROR', str(e))


@enterprise_bp.route('/datasets/<int:dataset_id>', methods=['GET'])
@RoleManager.require_permission('predict')
def get_dataset(dataset_id):
    """Get dataset details."""
    try:
        with get_db() as session:
            stats = StorageService.get_dataset_statistics(session, dataset_id)
            if not stats:
                return APIResponse.error('NOT_FOUND', 'Dataset not found'), 404
            
            return APIResponse.success(stats)
    except Exception as e:
        logger.error(f"Error fetching dataset: {str(e)}")
        return APIResponse.error('FETCH_ERROR', str(e))


@enterprise_bp.route('/datasets/<int:dataset_id>', methods=['DELETE'])
@RoleManager.require_permission('admin')
def delete_dataset(dataset_id):
    """Delete a dataset."""
    try:
        with get_db() as session:
            user = request.context.user
            success = StorageService.delete_dataset(session, dataset_id)
            
            if success:
                AuditService.log_action(
                    session,
                    user.id,
                    'DATASET_DELETE',
                    'TrafficData',
                    dataset_id
                )
                return APIResponse.success({'deleted': True})
            else:
                return APIResponse.error('NOT_FOUND', 'Dataset not found'), 404
    except Exception as e:
        logger.error(f"Error deleting dataset: {str(e)}")
        return APIResponse.error('DELETE_ERROR', str(e))


# ========================
# Prediction History
# ========================

@enterprise_bp.route('/predictions/history', methods=['GET'])
@RoleManager.require_permission('predict')
def get_prediction_history():
    """Get prediction history."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        days = request.args.get('days', 7, type=int)
        offset = (page - 1) * per_page
        
        with get_db() as session:
            start_date = datetime.utcnow() - timedelta(days=days)
            query = session.query(Prediction).filter(
                Prediction.created_at >= start_date
            ).order_by(Prediction.created_at.desc())
            
            total = query.count()
            predictions = query.limit(per_page).offset(offset).all()
            
            data = [{
                'id': p.id,
                'model_version': p.model_version,
                'latency_ms': float(p.latency_ms),
                'congestion_level': p.congestion_level,
                'status': p.status,
                'created_at': p.created_at.isoformat(),
                'user_id': p.user_id
            } for p in predictions]
            
            return APIResponse.paginated(data, total, page, per_page)
    except Exception as e:
        logger.error(f"Error fetching prediction history: {str(e)}")
        return APIResponse.error('FETCH_ERROR', str(e))


@enterprise_bp.route('/predictions/stats', methods=['GET'])
@RoleManager.require_permission('predict')
def get_prediction_stats():
    """Get prediction statistics."""
    try:
        # Try cache first
        cached = CacheService.get_analytics('predictions_stats')
        if cached:
            return APIResponse.success(cached)
        
        with get_db() as session:
            total = session.query(Prediction).count()
            successful = session.query(Prediction).filter_by(status='SUCCESSFUL').count()
            failed = session.query(Prediction).filter_by(status='FAILED').count()
            
            # Calculate average latency
            from sqlalchemy import func
            avg_latency = session.query(func.avg(Prediction.latency_ms)).filter(
                Prediction.status == 'SUCCESSFUL'
            ).scalar()
            
            stats = {
                'total_predictions': total,
                'successful': successful,
                'failed': failed,
                'success_rate': (successful / total * 100) if total > 0 else 0,
                'average_latency_ms': float(avg_latency) if avg_latency else 0
            }
            
            CacheService.cache_analytics('predictions_stats', stats)
            return APIResponse.success(stats)
    except Exception as e:
        logger.error(f"Error fetching prediction stats: {str(e)}")
        return APIResponse.error('FETCH_ERROR', str(e))


# ========================
# Optimization History
# ========================

@enterprise_bp.route('/optimizations/history', methods=['GET'])
@RoleManager.require_permission('optimize')
def get_optimization_history():
    """Get optimization history."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        days = request.args.get('days', 7, type=int)
        offset = (page - 1) * per_page
        
        with get_db() as session:
            start_date = datetime.utcnow() - timedelta(days=days)
            query = session.query(Optimization).filter(
                Optimization.created_at >= start_date
            ).order_by(Optimization.created_at.desc())
            
            total = query.count()
            optimizations = query.limit(per_page).offset(offset).all()
            
            data = [{
                'id': o.id,
                'fitness_score': float(o.fitness_score),
                'duration_ms': float(o.duration_ms),
                'iterations_completed': o.iterations_completed,
                'status': o.status,
                'created_at': o.created_at.isoformat(),
                'user_id': o.user_id
            } for o in optimizations]
            
            return APIResponse.paginated(data, total, page, per_page)
    except Exception as e:
        logger.error(f"Error fetching optimization history: {str(e)}")
        return APIResponse.error('FETCH_ERROR', str(e))


@enterprise_bp.route('/optimizations/best', methods=['GET'])
@RoleManager.require_permission('optimize')
def get_best_optimizations():
    """Get best optimizations."""
    try:
        limit = request.args.get('limit', 10, type=int)
        
        with get_db() as session:
            best = session.query(Optimization).filter(
                Optimization.status == 'SUCCESSFUL'
            ).order_by(Optimization.fitness_score.desc()).limit(limit).all()
            
            data = [{
                'id': o.id,
                'fitness_score': float(o.fitness_score),
                'duration_ms': float(o.duration_ms),
                'created_at': o.created_at.isoformat()
            } for o in best]
            
            return APIResponse.success(data)
    except Exception as e:
        logger.error(f"Error fetching best optimizations: {str(e)}")
        return APIResponse.error('FETCH_ERROR', str(e))


# ========================
# Analytics
# ========================

@enterprise_bp.route('/analytics/overview', methods=['GET'])
@RoleManager.require_permission('predict')
def get_analytics_overview():
    """Get analytics overview."""
    try:
        # Try cache first
        cached = CacheService.get_analytics('overview')
        if cached:
            return APIResponse.success(cached)
        
        with get_db() as session:
            stats = AnalyticsService.get_overview_stats(session)
            CacheService.cache_analytics('overview', stats)
            return APIResponse.success(stats)
    except Exception as e:
        logger.error(f"Error fetching analytics overview: {str(e)}")
        return APIResponse.error('FETCH_ERROR', str(e))


@enterprise_bp.route('/analytics/performance', methods=['GET'])
@RoleManager.require_permission('predict')
def get_performance_metrics():
    """Get performance metrics."""
    try:
        with get_db() as session:
            metrics = AnalyticsService.get_performance_metrics(session)
            return APIResponse.success(metrics)
    except Exception as e:
        logger.error(f"Error fetching performance metrics: {str(e)}")
        return APIResponse.error('FETCH_ERROR', str(e))


@enterprise_bp.route('/analytics/trends', methods=['GET'])
@RoleManager.require_permission('predict')
def get_trend_analysis():
    """Get trend analysis."""
    try:
        days = request.args.get('days', 30, type=int)
        
        with get_db() as session:
            trends = AnalyticsService.get_trend_analysis(session, days)
            return APIResponse.success(trends)
    except Exception as e:
        logger.error(f"Error fetching trends: {str(e)}")
        return APIResponse.error('FETCH_ERROR', str(e))


# ========================
# Audit Logs
# ========================

@enterprise_bp.route('/audit', methods=['GET'])
@RoleManager.require_permission('admin')
def get_audit_logs():
    """Get audit logs."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        action = request.args.get('action', None)
        offset = (page - 1) * per_page
        
        with get_db() as session:
            if action:
                logs, total = AuditService.get_action_audit_logs(
                    session, action, limit=per_page, offset=offset
                )
            else:
                query = session.query(AuditLog).order_by(AuditLog.created_at.desc())
                total = query.count()
                logs = query.limit(per_page).offset(offset).all()
            
            data = [{
                'id': log.id,
                'user_id': log.user_id,
                'action': log.action,
                'resource_type': log.resource_type,
                'resource_id': log.resource_id,
                'status': log.status,
                'created_at': log.created_at.isoformat()
            } for log in logs]
            
            return APIResponse.paginated(data, total, page, per_page)
    except Exception as e:
        logger.error(f"Error fetching audit logs: {str(e)}")
        return APIResponse.error('FETCH_ERROR', str(e))


# ========================
# Model Registry
# ========================

@enterprise_bp.route('/models', methods=['GET'])
@RoleManager.require_permission('predict')
def get_models():
    """Get registered models."""
    try:
        with get_db() as session:
            models = session.query(ModelRegistry).order_by(
                ModelRegistry.created_at.desc()
            ).all()
            
            data = [{
                'id': m.id,
                'name': m.name,
                'version': m.version,
                'model_type': m.model_type,
                'status': m.status,
                'is_current': m.is_current,
                'is_production': m.is_production,
                'created_at': m.created_at.isoformat()
            } for m in models]
            
            return APIResponse.success(data)
    except Exception as e:
        logger.error(f"Error fetching models: {str(e)}")
        return APIResponse.error('FETCH_ERROR', str(e))


@enterprise_bp.route('/models/current', methods=['GET'])
@RoleManager.require_permission('predict')
def get_current_model():
    """Get current active model."""
    try:
        with get_db() as session:
            model = session.query(ModelRegistry).filter_by(is_current=True).first()
            if not model:
                return APIResponse.error('NOT_FOUND', 'No current model'), 404
            
            data = {
                'id': model.id,
                'name': model.name,
                'version': model.version,
                'model_type': model.model_type,
                'metrics': model.metrics,
                'validation_score': float(model.validation_score) if model.validation_score else None,
                'is_production': model.is_production
            }
            
            return APIResponse.success(data)
    except Exception as e:
        logger.error(f"Error fetching current model: {str(e)}")
        return APIResponse.error('FETCH_ERROR', str(e))


@enterprise_bp.route('/models/<int:model_id>/activate', methods=['POST'])
@RoleManager.require_permission('admin')
def activate_model(model_id):
    """Activate a model."""
    try:
        with get_db() as session:
            # Deactivate current model
            current = session.query(ModelRegistry).filter_by(is_current=True).first()
            if current:
                current.is_current = False
                current.deactivated_at = datetime.utcnow()
            
            # Activate new model
            model = session.query(ModelRegistry).filter_by(id=model_id).first()
            if not model:
                return APIResponse.error('NOT_FOUND', 'Model not found'), 404
            
            model.is_current = True
            model.activated_at = datetime.utcnow()
            session.commit()
            
            return APIResponse.success({'activated': True})
    except Exception as e:
        logger.error(f"Error activating model: {str(e)}")
        return APIResponse.error('UPDATE_ERROR', str(e))


# ========================
# Data Export
# ========================

@enterprise_bp.route('/export/predictions', methods=['POST'])
@RoleManager.require_permission('predict')
def export_predictions():
    """Export predictions to CSV/JSON."""
    try:
        format_type = request.json.get('format', 'csv').lower()
        days = request.json.get('days', 7)
        
        if format_type not in ['csv', 'json', 'xlsx', 'pdf']:
            return APIResponse.error('INVALID_FORMAT', 'Unsupported format'), 400
        
        with get_db() as session:
            start_date = datetime.utcnow() - timedelta(days=days)
            predictions = session.query(Prediction).filter(
                Prediction.created_at >= start_date
            ).all()
            
            if format_type == 'json':
                data = [{
                    'id': p.id,
                    'model_version': p.model_version,
                    'latency_ms': float(p.latency_ms),
                    'congestion_level': p.congestion_level,
                    'created_at': p.created_at.isoformat()
                } for p in predictions]
                return APIResponse.success({'format': 'json', 'count': len(data), 'data': data})
            
            elif format_type == 'csv':
                import csv
                import io
                
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=['id', 'model_version', 'latency_ms', 'congestion_level', 'created_at'])
                writer.writeheader()
                
                for p in predictions:
                    writer.writerow({
                        'id': p.id,
                        'model_version': p.model_version,
                        'latency_ms': float(p.latency_ms),
                        'congestion_level': p.congestion_level,
                        'created_at': p.created_at.isoformat()
                    })
                
                return APIResponse.success({'format': 'csv', 'count': len(predictions), 'data': output.getvalue()})
            
            return APIResponse.success({'format': format_type, 'count': len(predictions)})
    except Exception as e:
        logger.error(f"Error exporting predictions: {str(e)}")
        return APIResponse.error('EXPORT_ERROR', str(e))


# ========================
# System Monitoring
# ========================

@enterprise_bp.route('/metrics', methods=['GET'])
def get_metrics():
    """Get system metrics."""
    try:
        from services.cache_service import CacheService
        
        metrics = {
            'cache_stats': CacheService.get_stats(),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return APIResponse.success(metrics)
    except Exception as e:
        logger.error(f"Error fetching metrics: {str(e)}")
        return APIResponse.error('FETCH_ERROR', str(e))


@enterprise_bp.route('/system-status', methods=['GET'])
def get_system_status():
    """Get system status."""
    try:
        from database.database import check_db_connection
        
        db_ok, db_msg = check_db_connection()
        
        status = {
            'timestamp': datetime.utcnow().isoformat(),
            'database': {
                'status': 'healthy' if db_ok else 'unhealthy',
                'message': db_msg
            },
            'cache': {
                'enabled': CacheService.is_enabled(),
                'status': 'healthy' if CacheService.is_enabled() else 'disabled'
            }
        }
        
        return APIResponse.success(status)
    except Exception as e:
        logger.error(f"Error fetching system status: {str(e)}")
        return APIResponse.error('FETCH_ERROR', str(e))
