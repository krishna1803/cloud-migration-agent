"""
Configuration management for the Cloud Migration Agent Platform.

Loads configuration from environment variables and provides
typed configuration objects.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class OCIConfig(BaseSettings):
    """OCI configuration"""
    region: str = Field(default="us-ashburn-1", alias="OCI_REGION")
    tenancy_id: str = Field(default="", alias="OCI_TENANCY_ID")
    user_id: str = Field(default="", alias="OCI_USER_ID")
    fingerprint: str = Field(default="", alias="OCI_FINGERPRINT")
    private_key_path: str = Field(default="~/.oci/oci_api_key.pem", alias="OCI_PRIVATE_KEY_PATH")
    compartment_id: str = Field(default="", alias="OCI_COMPARTMENT_ID")

    class Config:
        env_file = ".env"
        case_sensitive = False


class GenAIConfig(BaseSettings):
    """OCI Generative AI Service configuration"""
    endpoint: str = Field(
        default="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
        alias="OCI_GENAI_ENDPOINT"
    )
    model_id: str = Field(default="cohere.command-r-plus", alias="OCI_GENAI_MODEL_ID")
    embedding_model_id: str = Field(
        default="cohere.embed-english-v3.0",
        alias="OCI_GENAI_EMBEDDING_MODEL_ID"
    )
    max_tokens: int = Field(default=4096, alias="OCI_GENAI_MAX_TOKENS")
    temperature: float = Field(default=0.1, alias="OCI_GENAI_TEMPERATURE")

    class Config:
        env_file = ".env"
        case_sensitive = False


class DatabaseConfig(BaseSettings):
    """Oracle 23ai Vector Database configuration"""
    host: str = Field(default="localhost", alias="ORACLE_DB_HOST")
    port: int = Field(default=1521, alias="ORACLE_DB_PORT")
    service: str = Field(default="FREEPDB1", alias="ORACLE_DB_SERVICE")
    user: str = Field(default="", alias="ORACLE_DB_USER")
    password: str = Field(default="", alias="ORACLE_DB_PASSWORD")

    @property
    def connection_string(self) -> str:
        """Get database connection string"""
        return f"{self.user}/{self.password}@{self.host}:{self.port}/{self.service}"

    class Config:
        env_file = ".env"
        case_sensitive = False


class AppConfig(BaseSettings):
    """Application configuration"""
    name: str = Field(default="Cloud Migration Agent", alias="APP_NAME")
    version: str = Field(default="4.0.0", alias="APP_VERSION")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    checkpoint_enabled: bool = Field(default=False, alias="CHECKPOINT_ENABLED")
    tracing_enabled: bool = Field(default=True, alias="TRACING_ENABLED")

    # Thresholds
    discovery_confidence_threshold: float = Field(
        default=0.80,
        alias="DISCOVERY_CONFIDENCE_THRESHOLD"
    )
    review_approval_threshold: float = Field(
        default=0.90,
        alias="REVIEW_APPROVAL_THRESHOLD"
    )
    automated_approval_cost_limit: float = Field(
        default=0.0,
        alias="AUTOMATED_APPROVAL_COST_LIMIT"
    )

    # Feature Flags
    feature_parallel_tool_calls: bool = Field(default=True, alias="FEATURE_PARALLEL_TOOL_CALLS")
    feature_cost_optimization: bool = Field(default=True, alias="FEATURE_COST_OPTIMIZATION")
    feature_kb_integration: bool = Field(default=True, alias="FEATURE_KB_INTEGRATION")
    feature_vector_search: bool = Field(default=True, alias="FEATURE_VECTOR_SEARCH")
    feature_dual_review_gates: bool = Field(default=True, alias="FEATURE_DUAL_REVIEW_GATES")
    feature_risk_analysis: bool = Field(default=True, alias="FEATURE_RISK_ANALYSIS")
    feature_mcp_health: bool = Field(default=True, alias="FEATURE_MCP_HEALTH")

    # Storage
    upload_dir: str = Field(default="./uploads", alias="UPLOAD_DIR")
    export_dir: str = Field(default="./exports", alias="EXPORT_DIR")
    checkpoint_dir: str = Field(default="./checkpoints", alias="CHECKPOINT_DIR")

    class Config:
        env_file = ".env"
        case_sensitive = False


class MCPConfig(BaseSettings):
    """MCP Server configuration"""
    kb_server_url: str = Field(default="http://localhost:8001", alias="MCP_KB_SERVER_URL")
    docs_server_url: str = Field(default="http://localhost:8002", alias="MCP_DOCS_SERVER_URL")
    xls_finops_server_url: str = Field(default="http://localhost:8003", alias="MCP_XLS_FINOPS_SERVER_URL")
    mapping_server_url: str = Field(default="http://localhost:8004", alias="MCP_MAPPING_SERVER_URL")
    refarch_server_url: str = Field(default="http://localhost:8005", alias="MCP_REFARCH_SERVER_URL")
    sizing_server_url: str = Field(default="http://localhost:8006", alias="MCP_SIZING_SERVER_URL")
    pricing_server_url: str = Field(default="http://localhost:8007", alias="MCP_PRICING_SERVER_URL")
    deliverables_server_url: str = Field(default="http://localhost:8008", alias="MCP_DELIVERABLES_SERVER_URL")
    terraform_gen_server_url: str = Field(default="http://localhost:8009", alias="MCP_TERRAFORM_GEN_SERVER_URL")
    oci_rm_server_url: str = Field(default="http://localhost:8010", alias="MCP_OCI_RM_SERVER_URL")

    class Config:
        env_file = ".env"
        case_sensitive = False


class APIConfig(BaseSettings):
    """API Server configuration"""
    host: str = Field(default="0.0.0.0", alias="API_HOST")
    port: int = Field(default=8000, alias="API_PORT")
    workers: int = Field(default=4, alias="API_WORKERS")

    class Config:
        env_file = ".env"
        case_sensitive = False


class UIConfig(BaseSettings):
    """UI configuration"""
    host: str = Field(default="0.0.0.0", alias="UI_HOST")
    port: int = Field(default=7860, alias="UI_PORT")
    share: bool = Field(default=False, alias="UI_SHARE")

    class Config:
        env_file = ".env"
        case_sensitive = False


class Config:
    """Main configuration container"""

    def __init__(self):
        """Initialize all configuration sections"""
        self.oci = OCIConfig()
        self.genai = GenAIConfig()
        self.database = DatabaseConfig()
        self.app = AppConfig()
        self.mcp = MCPConfig()
        self.api = APIConfig()
        self.ui = UIConfig()

        # Create necessary directories
        self._create_directories()

    def _create_directories(self):
        """Create necessary directories if they don't exist"""
        os.makedirs(self.app.upload_dir, exist_ok=True)
        os.makedirs(self.app.export_dir, exist_ok=True)
        os.makedirs(self.app.checkpoint_dir, exist_ok=True)


# Global configuration instance
config = Config()
