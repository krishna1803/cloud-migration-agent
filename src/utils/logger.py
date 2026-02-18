"""
Logging utilities for the Cloud Migration Agent Platform.

Provides structured logging with JSON formatting and
integration with OpenTelemetry for tracing.
"""

import logging
import sys
from typing import Any, Dict, Optional
from datetime import datetime
from pythonjsonlogger import jsonlogger

# Maximum characters logged for large text fields (prompts, responses, TF code)
_MAX_PREVIEW = 800


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


# ── NEW: Workflow observability helpers ──────────────────────────────────────


def log_node_entry(
    migration_id: str,
    phase: str,
    node: str,
    inputs: Optional[Dict[str, Any]] = None,
    logger_instance: Optional[logging.Logger] = None,
) -> None:
    """Log node entry with key input fields for workflow tracing."""
    _log = logger_instance or logger
    _log.info(
        f"[{phase.upper()}:{node}] ENTER",
        extra={
            "event_type": "node_entry",
            "migration_id": migration_id,
            "phase": phase,
            "node": node,
            "inputs": {k: str(v)[:200] for k, v in (inputs or {}).items()},
        },
    )


def log_node_exit(
    migration_id: str,
    phase: str,
    node: str,
    outputs: Optional[Dict[str, Any]] = None,
    duration_ms: Optional[float] = None,
    logger_instance: Optional[logging.Logger] = None,
) -> None:
    """Log node exit with key output fields and wall-clock duration."""
    _log = logger_instance or logger
    dur = f" [{duration_ms:.0f}ms]" if duration_ms is not None else ""
    _log.info(
        f"[{phase.upper()}:{node}] EXIT{dur}",
        extra={
            "event_type": "node_exit",
            "migration_id": migration_id,
            "phase": phase,
            "node": node,
            "outputs": {k: str(v)[:200] for k, v in (outputs or {}).items()},
            "duration_ms": round(duration_ms, 1) if duration_ms is not None else None,
        },
    )


def log_mcp_call(
    migration_id: str,
    server: str,
    method: str,
    inputs: Optional[Dict[str, Any]] = None,
    result: Optional[Dict[str, Any]] = None,
    duration_ms: Optional[float] = None,
    logger_instance: Optional[logging.Logger] = None,
) -> None:
    """Log an MCP server invocation — inputs, result summary, and latency."""
    _log = logger_instance or logger

    def _summarise(d: Optional[Dict]) -> Dict:
        if not d:
            return {}
        out = {}
        for k, v in d.items():
            sv = str(v)
            out[k] = sv[:300] if len(sv) > 300 else sv
        return out

    dur = f" [{duration_ms:.0f}ms]" if duration_ms is not None else ""
    _log.info(
        f"[MCP:{server}.{method}]{dur}",
        extra={
            "event_type": "mcp_call",
            "migration_id": migration_id,
            "mcp_server": server,
            "mcp_method": method,
            "mcp_inputs": _summarise(inputs),
            "mcp_result": _summarise(result),
            "duration_ms": round(duration_ms, 1) if duration_ms is not None else None,
        },
    )


def log_llm_call(
    migration_id: str,
    node: str,
    prompt_preview: str = "",
    response_preview: str = "",
    duration_ms: Optional[float] = None,
    logger_instance: Optional[logging.Logger] = None,
) -> None:
    """Log an LLM invocation — prompt preview, response preview, and latency."""
    _log = logger_instance or logger
    dur = f" [{duration_ms:.0f}ms]" if duration_ms is not None else ""
    _log.info(
        f"[LLM:{node}]{dur}",
        extra={
            "event_type": "llm_call",
            "migration_id": migration_id,
            "node": node,
            "prompt_chars": len(prompt_preview),
            "prompt_preview": prompt_preview[:_MAX_PREVIEW],
            "response_chars": len(response_preview),
            "response_preview": response_preview[:_MAX_PREVIEW],
            "duration_ms": round(duration_ms, 1) if duration_ms is not None else None,
        },
    )
