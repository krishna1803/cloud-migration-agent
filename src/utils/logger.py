"""
Logging utilities for the Cloud Migration Agent Platform.

Provides structured logging with JSON formatting and
integration with OpenTelemetry for tracing.
"""

import logging
import sys
from typing import Optional
from datetime import datetime
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with timestamp"""
    
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name


def setup_logger(
    name: str,
    level: str = "INFO",
    json_format: bool = True
) -> logging.Logger:
    """
    Set up a logger with appropriate formatting.
    
    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON formatting if True
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    logger.handlers = []
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))
    
    # Set formatter
    if json_format:
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger


# Create default logger
logger = setup_logger("cloud_migration_agent")


def log_phase_transition(
    migration_id: str,
    from_phase: str,
    to_phase: str,
    logger_instance: Optional[logging.Logger] = None
):
    """Log phase transition event"""
    log = logger_instance or logger
    log.info(
        "Phase transition",
        extra={
            "migration_id": migration_id,
            "from_phase": from_phase,
            "to_phase": to_phase,
            "event_type": "phase_transition"
        }
    )


def log_review_gate(
    migration_id: str,
    gate_name: str,
    decision: str,
    logger_instance: Optional[logging.Logger] = None
):
    """Log review gate decision"""
    log = logger_instance or logger
    log.info(
        "Review gate decision",
        extra={
            "migration_id": migration_id,
            "gate_name": gate_name,
            "decision": decision,
            "event_type": "review_gate"
        }
    )


def log_tool_call(
    migration_id: str,
    tool_name: str,
    status: str,
    duration_ms: Optional[float] = None,
    logger_instance: Optional[logging.Logger] = None
):
    """Log tool call event"""
    log = logger_instance or logger
    extra = {
        "migration_id": migration_id,
        "tool_name": tool_name,
        "status": status,
        "event_type": "tool_call"
    }
    if duration_ms is not None:
        extra["duration_ms"] = duration_ms
    
    log.info("Tool call", extra=extra)


def log_checkpoint_save(
    migration_id: str,
    phase: str,
    node: str,
    logger_instance: Optional[logging.Logger] = None
):
    """Log checkpoint save event"""
    log = logger_instance or logger
    log.info(
        "Checkpoint saved",
        extra={
            "migration_id": migration_id,
            "phase": phase,
            "node": node,
            "event_type": "checkpoint_save"
        }
    )


def log_error(
    migration_id: str,
    error_type: str,
    error_message: str,
    phase: Optional[str] = None,
    logger_instance: Optional[logging.Logger] = None
):
    """Log error event"""
    log = logger_instance or logger
    extra = {
        "migration_id": migration_id,
        "error_type": error_type,
        "error_message": error_message,
        "event_type": "error"
    }
    if phase:
        extra["phase"] = phase
    
    log.error("Error occurred", extra=extra)
