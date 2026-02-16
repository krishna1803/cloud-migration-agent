"""
Checkpoint manager for persisting migration state to Oracle 23ai.

Implements LangGraph checkpointing interface with Oracle DB backend.
Falls back to in-memory storage when Oracle DB is unavailable.
"""

import json
from typing import Optional, Dict, Any
from datetime import datetime

from src.models.state_schema import MigrationState
from src.utils.config import config
from src.utils.logger import logger


class InMemoryCheckpointSaver:
    """
    In-memory checkpoint saver fallback.

    Used when Oracle DB is not available.
    """

    def __init__(self):
        self._checkpoints: Dict[str, list] = {}
        self._migrations: Dict[str, Dict[str, Any]] = {}
        logger.info("Using in-memory checkpoint saver (no Oracle DB)")

    def put(
        self,
        config_dict: Dict[str, Any],
        checkpoint: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        migration_id = config_dict.get("configurable", {}).get("migration_id")
        if not migration_id:
            raise ValueError("migration_id required in config")

        checkpoint_id = f"{migration_id}_{datetime.utcnow().isoformat()}"
        state_data = checkpoint.get("channel_values", {})
        node = checkpoint.get("node", "unknown")
        phase = state_data.get("current_phase", "unknown")

        entry = {
            "checkpoint_id": checkpoint_id,
            "migration_id": migration_id,
            "phase": phase,
            "node": node,
            "state_data": state_data,
            "metadata": metadata,
            "created_at": datetime.utcnow().isoformat()
        }

        if migration_id not in self._checkpoints:
            self._checkpoints[migration_id] = []
        self._checkpoints[migration_id].append(entry)

        return {
            "configurable": {
                "migration_id": migration_id,
                "checkpoint_id": checkpoint_id
            }
        }

    def get(self, config_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        migration_id = config_dict.get("configurable", {}).get("migration_id")
        if not migration_id or migration_id not in self._checkpoints:
            return None

        entries = self._checkpoints[migration_id]
        if not entries:
            return None

        latest = entries[-1]
        return {
            "checkpoint_id": latest["checkpoint_id"],
            "node": latest["node"],
            "channel_values": latest["state_data"],
            "metadata": latest.get("metadata", {}),
            "created_at": latest["created_at"]
        }

    def list(self, config_dict: Dict[str, Any], limit: int = 10) -> list:
        migration_id = config_dict.get("configurable", {}).get("migration_id")
        if not migration_id or migration_id not in self._checkpoints:
            return []
        entries = self._checkpoints[migration_id]
        return list(reversed(entries[-limit:]))

    def get_migration_state(self, migration_id: str) -> Optional[MigrationState]:
        checkpoint = self.get({"configurable": {"migration_id": migration_id}})
        if checkpoint:
            return MigrationState(**checkpoint["channel_values"])
        return None

    def save_migration_state(self, migration_id: str, state: MigrationState, node: str = "manual_save"):
        self.put(
            config_dict={"configurable": {"migration_id": migration_id}},
            checkpoint={"node": node, "channel_values": state.model_dump()}
        )

    def close(self):
        pass


class OracleCheckpointSaver:
    """
    Oracle 23ai-based checkpoint saver for LangGraph.
    """

    def __init__(self):
        self.connection = None
        self._connect()
        self._create_tables()

    def _connect(self):
        try:
            import oracledb
            self.connection = oracledb.connect(
                user=config.database.user,
                password=config.database.password,
                dsn=f"{config.database.host}:{config.database.port}/{config.database.service}"
            )
            logger.info("Connected to Oracle database for checkpoints")
        except Exception as e:
            logger.error(f"Failed to connect to Oracle database: {str(e)}")
            raise

    def _create_tables(self):
        try:
            cursor = self.connection.cursor()
            for ddl in [
                """CREATE TABLE migrations (
                    migration_id VARCHAR2(100) PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    current_phase VARCHAR2(50),
                    phase_status VARCHAR2(50),
                    source_provider VARCHAR2(50),
                    target_region VARCHAR2(50))""",
                """CREATE TABLE migration_checkpoints (
                    checkpoint_id VARCHAR2(100) PRIMARY KEY,
                    migration_id VARCHAR2(100) NOT NULL,
                    phase VARCHAR2(50) NOT NULL,
                    node VARCHAR2(100) NOT NULL,
                    state_data CLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata CLOB)""",
                """CREATE TABLE migration_state_history (
                    history_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    migration_id VARCHAR2(100) NOT NULL,
                    checkpoint_id VARCHAR2(100) NOT NULL,
                    phase VARCHAR2(50) NOT NULL,
                    node VARCHAR2(100) NOT NULL,
                    state_data CLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
            ]:
                try:
                    cursor.execute(ddl)
                except Exception:
                    pass  # Table already exists
            self.connection.commit()
            logger.info("Checkpoint tables created/verified")
        except Exception as e:
            logger.error(f"Error creating checkpoint tables: {str(e)}")

    def put(self, config_dict, checkpoint, metadata=None):
        try:
            migration_id = config_dict.get("configurable", {}).get("migration_id")
            if not migration_id:
                raise ValueError("migration_id required")
            checkpoint_id = f"{migration_id}_{datetime.utcnow().isoformat()}"
            state_data = checkpoint.get("channel_values", {})
            phase = state_data.get("current_phase", "unknown")
            node = checkpoint.get("node", "unknown")
            cursor = self.connection.cursor()
            cursor.execute(
                "INSERT INTO migration_checkpoints (checkpoint_id, migration_id, phase, node, state_data, metadata) VALUES (:1,:2,:3,:4,:5,:6)",
                (checkpoint_id, migration_id, phase, node, json.dumps(state_data), json.dumps(metadata) if metadata else None)
            )
            cursor.execute(
                "INSERT INTO migration_state_history (migration_id, checkpoint_id, phase, node, state_data) VALUES (:1,:2,:3,:4,:5)",
                (migration_id, checkpoint_id, phase, node, json.dumps(state_data))
            )
            self.connection.commit()
            return {"configurable": {"migration_id": migration_id, "checkpoint_id": checkpoint_id}}
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {str(e)}")
            self.connection.rollback()
            raise

    def get(self, config_dict):
        try:
            migration_id = config_dict.get("configurable", {}).get("migration_id")
            if not migration_id:
                return None
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT checkpoint_id, phase, node, state_data, metadata, created_at FROM migration_checkpoints WHERE migration_id = :1 ORDER BY created_at DESC FETCH FIRST 1 ROWS ONLY",
                (migration_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            checkpoint_id, phase, node, state_json, metadata_json, created_at = row
            return {
                "checkpoint_id": checkpoint_id, "node": node,
                "channel_values": json.loads(state_json),
                "metadata": json.loads(metadata_json) if metadata_json else {},
                "created_at": created_at.isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to retrieve checkpoint: {str(e)}")
            return None

    def list(self, config_dict, limit=10):
        try:
            migration_id = config_dict.get("configurable", {}).get("migration_id")
            if not migration_id:
                return []
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT checkpoint_id, phase, node, state_data, metadata, created_at FROM migration_checkpoints WHERE migration_id = :1 ORDER BY created_at DESC FETCH FIRST :2 ROWS ONLY",
                (migration_id, limit)
            )
            return [
                {"checkpoint_id": r[0], "node": r[2], "phase": r[1], "channel_values": json.loads(r[3]),
                 "metadata": json.loads(r[4]) if r[4] else {}, "created_at": r[5].isoformat()}
                for r in cursor
            ]
        except Exception as e:
            logger.error(f"Failed to list checkpoints: {str(e)}")
            return []

    def get_migration_state(self, migration_id):
        checkpoint = self.get({"configurable": {"migration_id": migration_id}})
        if checkpoint:
            return MigrationState(**checkpoint["channel_values"])
        return None

    def save_migration_state(self, migration_id, state, node="manual_save"):
        self.put(
            config_dict={"configurable": {"migration_id": migration_id}},
            checkpoint={"node": node, "channel_values": state.model_dump()}
        )

    def close(self):
        if self.connection:
            self.connection.close()


def _create_checkpoint_saver():
    """Create the appropriate checkpoint saver based on configuration."""
    if config.app.checkpoint_enabled:
        try:
            return OracleCheckpointSaver()
        except Exception as e:
            logger.warning(f"Oracle checkpoint unavailable, using in-memory: {e}")
            return InMemoryCheckpointSaver()
    return InMemoryCheckpointSaver()


# Global checkpoint saver instance
checkpoint_saver = _create_checkpoint_saver()
