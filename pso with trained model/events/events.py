"""
Event system architecture.

Supports:
- Event publishing
- Event subscription
- Event handlers
- Future Kafka integration in Phase 5

Events:
- PredictionCreated
- OptimizationCompleted
- DatasetUploaded
- ReportGenerated
- SettingsChanged
"""

from datetime import datetime
from typing import Dict, Any, List, Callable, Optional
from enum import Enum
import json
from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)


class EventType(str, Enum):
    """Event types."""
    PREDICTION_CREATED = "prediction.created"
    OPTIMIZATION_COMPLETED = "optimization.completed"
    DATASET_UPLOADED = "dataset.uploaded"
    REPORT_GENERATED = "report.generated"
    SETTINGS_CHANGED = "settings.changed"
    USER_LOGGED_IN = "user.logged_in"
    MODEL_ACTIVATED = "model.activated"


class Event:
    """Base event class."""
    
    def __init__(self, event_type: EventType, data: Dict[str, Any], user_id: Optional[int] = None):
        self.event_type = event_type
        self.data = data
        self.user_id = user_id
        self.timestamp = datetime.utcnow()
        self.event_id = f"{event_type}:{datetime.utcnow().timestamp()}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data
        }
    
    def to_json(self) -> str:
        """Convert event to JSON."""
        return json.dumps(self.to_dict(), default=str)


class PredictionCreatedEvent(Event):
    """Event fired when prediction is created."""
    
    def __init__(self, prediction_id: int, model_version: str, user_id: int, latency_ms: float):
        data = {
            'prediction_id': prediction_id,
            'model_version': model_version,
            'latency_ms': latency_ms
        }
        super().__init__(EventType.PREDICTION_CREATED, data, user_id)


class OptimizationCompletedEvent(Event):
    """Event fired when optimization is completed."""
    
    def __init__(self, optimization_id: int, fitness_score: float, user_id: int, duration_ms: float):
        data = {
            'optimization_id': optimization_id,
            'fitness_score': fitness_score,
            'duration_ms': duration_ms
        }
        super().__init__(EventType.OPTIMIZATION_COMPLETED, data, user_id)


class DatasetUploadedEvent(Event):
    """Event fired when dataset is uploaded."""
    
    def __init__(self, dataset_id: int, filename: str, row_count: int, user_id: int):
        data = {
            'dataset_id': dataset_id,
            'filename': filename,
            'row_count': row_count
        }
        super().__init__(EventType.DATASET_UPLOADED, data, user_id)


class ReportGeneratedEvent(Event):
    """Event fired when report is generated."""
    
    def __init__(self, report_id: int, title: str, format_type: str, user_id: int):
        data = {
            'report_id': report_id,
            'title': title,
            'format': format_type
        }
        super().__init__(EventType.REPORT_GENERATED, data, user_id)


class SettingsChangedEvent(Event):
    """Event fired when settings are changed."""
    
    def __init__(self, setting_key: str, old_value: Any, new_value: Any, user_id: int):
        data = {
            'setting_key': setting_key,
            'old_value': old_value,
            'new_value': new_value
        }
        super().__init__(EventType.SETTINGS_CHANGED, data, user_id)


class EventBus:
    """Event publishing and subscription system."""
    
    _subscribers: Dict[EventType, List[Callable]] = {}
    _event_history: List[Event] = []
    _max_history = 1000
    
    @classmethod
    def subscribe(cls, event_type: EventType, handler: Callable) -> None:
        """Subscribe to an event type."""
        if event_type not in cls._subscribers:
            cls._subscribers[event_type] = []
        
        cls._subscribers[event_type].append(handler)
        logger.debug(f"✓ Handler subscribed to {event_type.value}")
    
    @classmethod
    def unsubscribe(cls, event_type: EventType, handler: Callable) -> None:
        """Unsubscribe from an event type."""
        if event_type in cls._subscribers:
            try:
                cls._subscribers[event_type].remove(handler)
                logger.debug(f"✓ Handler unsubscribed from {event_type.value}")
            except ValueError:
                pass
    
    @classmethod
    def publish(cls, event: Event) -> None:
        """Publish an event to all subscribers."""
        try:
            # Store in history
            cls._event_history.append(event)
            if len(cls._event_history) > cls._max_history:
                cls._event_history.pop(0)
            
            # Call all subscribers
            handlers = cls._subscribers.get(event.event_type, [])
            for handler in handlers:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Error in event handler: {str(e)}")
            
            logger.debug(f"✓ Event published: {event.event_type.value} (handlers: {len(handlers)})")
            
        except Exception as e:
            logger.error(f"Error publishing event: {str(e)}")
    
    @classmethod
    def get_history(cls, event_type: Optional[EventType] = None, limit: int = 100) -> List[Event]:
        """Get event history."""
        if event_type:
            events = [e for e in cls._event_history if e.event_type == event_type]
        else:
            events = cls._event_history
        
        return events[-limit:]
    
    @classmethod
    def clear_history(cls) -> None:
        """Clear event history."""
        cls._event_history.clear()
        logger.info("✓ Event history cleared")


# Event handlers that can be registered
def on_prediction_created(event: Event) -> None:
    """Handle prediction created event."""
    logger.info(f"Prediction created: {event.data['prediction_id']}")


def on_optimization_completed(event: Event) -> None:
    """Handle optimization completed event."""
    logger.info(f"Optimization completed: {event.data['optimization_id']}")


def on_dataset_uploaded(event: Event) -> None:
    """Handle dataset uploaded event."""
    logger.info(f"Dataset uploaded: {event.data['filename']}")


def on_report_generated(event: Event) -> None:
    """Handle report generated event."""
    logger.info(f"Report generated: {event.data['title']}")
