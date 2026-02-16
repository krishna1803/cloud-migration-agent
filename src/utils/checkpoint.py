"""
Checkpoint manager for persisting migration state to Oracle 23ai.

Implements LangGraph checkpointing interface with Oracle DB backend.
"""

import json
import oracledb
from typing import Optional, Dict, Any
from datetime import datetime
from langgraph.checkpoint import BaseCheckpointSaver

from src.models.state_schema import MigrationState
from src.utils.config import config
from src.utils.logger import logger


class OracleCheckpointSaver(BaseCheckpointSaver):
    """
    Oracle 23ai-based checkpoint saver for LangGraph.
    
    Stores migration state in Oracle database with
    support for versioning and rollback.
    """
    
    def __init__(self):
        """Initialize Oracle checkpoint saver"""
        self.connection = None
        self._connect()
        self._create_tables()
    
    def _connect(self):
        """Establish connection to Oracle database"""
        try:
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
        """Create checkpoint tables if they don't exist"""
        try:
            cursor = self.connection.cursor()
            
            # Checkpoints table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migration_checkpoints (
                    checkpoint_id VARCHAR2(100) PRIMARY KEY,
                    migration_id VARCHAR2(100) NOT NULL,
                    phase VARCHAR2(50) NOT NULL,
                    node VARCHAR2(100) NOT NULL,
                    state_data CLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata CLOB,
                    CONSTRAINT fk_migration 
                        FOREIGN KEY (migration_id) 
                        REFERENCES migrations(migration_id)
                )
            """)
            
            # Migrations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    migration_id VARCHAR2(100) PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    current_phase VARCHAR2(50),
                    phase_status VARCHAR2(50),
                    source_provider VARCHAR2(50),
                    target_region VARCHAR2(50)
                )
            """)
            
            # State history for audit trail
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migration_state_history (
                    history_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    migration_id VARCHAR2(100) NOT NULL,
                    checkpoint_id VARCHAR2(100) NOT NULL,
                    phase VARCHAR2(50) NOT NULL,
                    node VARCHAR2(100) NOT NULL,
                    state_data CLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_migration_history 
                        FOREIGN KEY (migration_id) 
                        REFERENCES migrations(migration_id)
                )
            """)
            
            self.connection.commit()
            logger.info("Checkpoint tables created/verified")
            
        except oracledb.DatabaseError as e:
            # Tables might already exist, which is fine
            error_code, = e.args
            if "ORA-00955" in str(error_code):  # Table already exists
                logger.info("Checkpoint tables already exist")
            else:
                logger.error(f"Error creating checkpoint tables: {str(e)}")
                raise
    
    def put(
        self,
        config: Dict[str, Any],
        checkpoint: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Save a checkpoint.
        
        Args:
            config: Configuration dict with migration_id
            checkpoint: Checkpoint data to save
            metadata: Optional metadata
            
        Returns:
            Saved checkpoint config
        """
        try:
            migration_id = config.get("configurable", {}).get("migration_id")
            if not migration_id:
                raise ValueError("migration_id required in config")
            
            # Generate checkpoint ID
            checkpoint_id = f"{migration_id}_{datetime.utcnow().isoformat()}"
            
            # Extract state from checkpoint
            state_data = checkpoint.get("channel_values", {})
            phase = state_data.get("current_phase", "unknown")
            node = checkpoint.get("node", "unknown")
            
            cursor = self.connection.cursor()
            
            # Insert checkpoint
            cursor.execute("""
                INSERT INTO migration_checkpoints 
                (checkpoint_id, migration_id, phase, node, state_data, metadata)
                VALUES (:1, :2, :3, :4, :5, :6)
            """, (
                checkpoint_id,
                migration_id,
                phase,
                node,
                json.dumps(state_data),
                json.dumps(metadata) if metadata else None
            ))
            
            # Update migration record
            cursor.execute("""
                MERGE INTO migrations m
                USING (SELECT :1 AS migration_id FROM dual) s
                ON (m.migration_id = s.migration_id)
                WHEN MATCHED THEN
                    UPDATE SET 
                        updated_at = CURRENT_TIMESTAMP,
                        current_phase = :2,
                        phase_status = :3
                WHEN NOT MATCHED THEN
                    INSERT (migration_id, current_phase, phase_status, 
                            source_provider, target_region)
                    VALUES (:1, :2, :3, :4, :5)
            """, (
                migration_id,
                phase,
                state_data.get("phase_status", "in_progress"),
                state_data.get("source_provider", ""),
                state_data.get("target_region", "us-ashburn-1")
            ))
            
            # Add to history
            cursor.execute("""
                INSERT INTO migration_state_history 
                (migration_id, checkpoint_id, phase, node, state_data)
                VALUES (:1, :2, :3, :4, :5)
            """, (
                migration_id,
                checkpoint_id,
                phase,
                node,
                json.dumps(state_data)
            ))
            
            self.connection.commit()
            
            logger.info(
                f"Checkpoint saved: {checkpoint_id} for migration {migration_id}"
            )
            
            return {
                "configurable": {
                    "migration_id": migration_id,
                    "checkpoint_id": checkpoint_id
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {str(e)}")
            self.connection.rollback()
            raise
    
    def get(
        self,
        config: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve the latest checkpoint for a migration.
        
        Args:
            config: Configuration dict with migration_id
            
        Returns:
            Checkpoint data or None if not found
        """
        try:
            migration_id = config.get("configurable", {}).get("migration_id")
            if not migration_id:
                return None
            
            cursor = self.connection.cursor()
            
            # Get latest checkpoint
            cursor.execute("""
                SELECT checkpoint_id, phase, node, state_data, metadata, created_at
                FROM migration_checkpoints
                WHERE migration_id = :1
                ORDER BY created_at DESC
                FETCH FIRST 1 ROWS ONLY
            """, (migration_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            checkpoint_id, phase, node, state_json, metadata_json, created_at = row
            
            return {
                "checkpoint_id": checkpoint_id,
                "node": node,
                "channel_values": json.loads(state_json),
                "metadata": json.loads(metadata_json) if metadata_json else {},
                "created_at": created_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to retrieve checkpoint: {str(e)}")
            return None
    
    def list(
        self,
        config: Dict[str, Any],
        limit: int = 10
    ) -> list:
        """
        List checkpoints for a migration.
        
        Args:
            config: Configuration dict with migration_id
            limit: Maximum number of checkpoints to return
            
        Returns:
            List of checkpoints
        """
        try:
            migration_id = config.get("configurable", {}).get("migration_id")
            if not migration_id:
                return []
            
            cursor = self.connection.cursor()
            
            cursor.execute("""
                SELECT checkpoint_id, phase, node, state_data, metadata, created_at
                FROM migration_checkpoints
                WHERE migration_id = :1
                ORDER BY created_at DESC
                FETCH FIRST :2 ROWS ONLY
            """, (migration_id, limit))
            
            checkpoints = []
            for row in cursor:
                checkpoint_id, phase, node, state_json, metadata_json, created_at = row
                checkpoints.append({
                    "checkpoint_id": checkpoint_id,
                    "node": node,
                    "phase": phase,
                    "channel_values": json.loads(state_json),
                    "metadata": json.loads(metadata_json) if metadata_json else {},
                    "created_at": created_at.isoformat()
                })
            
            return checkpoints
            
        except Exception as e:
            logger.error(f"Failed to list checkpoints: {str(e)}")
            return []
    
    def get_migration_state(self, migration_id: str) -> Optional[MigrationState]:
        """
        Get the current state of a migration.
        
        Args:
            migration_id: Migration ID
            
        Returns:
            MigrationState object or None
        """
        checkpoint = self.get({
            "configurable": {"migration_id": migration_id}
        })
        
        if checkpoint:
            state_data = checkpoint["channel_values"]
            return MigrationState(**state_data)
        
        return None
    
    def save_migration_state(
        self,
        migration_id: str,
        state: MigrationState,
        node: str = "manual_save"
    ):
        """
        Manually save migration state.
        
        Args:
            migration_id: Migration ID
            state: MigrationState to save
            node: Node name for this save
        """
        self.put(
            config={"configurable": {"migration_id": migration_id}},
            checkpoint={
                "node": node,
                "channel_values": state.dict()
            }
        )
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Oracle checkpoint saver connection closed")


# Global checkpoint saver instance
checkpoint_saver = OracleCheckpointSaver() if config.app.checkpoint_enabled else None
