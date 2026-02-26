"""
MCP Tool Servers for the Cloud Migration Agent Platform (v4.1.0).

16 MCP servers implementing the official MCP protocol:
  Group 1 — Knowledge & Documentation:
    KBServer, DocsServer, XlsFinOpsServer
  Group 2 — Service Mapping & Reference Architecture:
    MappingServer, RefArchServer, OracleArchHubServer, OracleLiveLabsServer
  Group 3 — Sizing & Pricing:
    SizingServer, PricingServer
  Group 4 — Infrastructure as Code:
    TerraformGenServer, TerraformValidatorServer, DependencyAnalysisServer
  Group 5 — Project Management & OCI Deployment:
    DeliverablesServer, ProjectExportServer, OCIResourceManagerServer,
    DeploymentMonitorServer
"""

from .kb_server import KBServer
from .docs_server import DocsServer
from .xls_finops_server import XlsFinOpsServer
from .mapping_server import MappingServer
from .refarch_server import RefArchServer
from .oracle_archhub_server import OracleArchHubServer
from .oracle_livelabs_server import OracleLiveLabsServer
from .sizing_server import SizingServer
from .pricing_server import PricingServer
from .terraform_gen_server import TerraformGenServer
from .terraform_validator_server import TerraformValidatorServer
from .dependency_analysis_server import DependencyAnalysisServer
from .deliverables_server import DeliverablesServer
from .project_export_server import ProjectExportServer
from .oci_rm_server import OCIResourceManagerServer
from .deployment_monitor_server import DeploymentMonitorServer

__all__ = [
    # Group 1 — Knowledge & Documentation
    "KBServer",
    "DocsServer",
    "XlsFinOpsServer",
    # Group 2 — Service Mapping & Reference Architecture
    "MappingServer",
    "RefArchServer",
    "OracleArchHubServer",
    "OracleLiveLabsServer",
    # Group 3 — Sizing & Pricing
    "SizingServer",
    "PricingServer",
    # Group 4 — Infrastructure as Code
    "TerraformGenServer",
    "TerraformValidatorServer",
    "DependencyAnalysisServer",
    # Group 5 — Project Management & OCI Deployment
    "DeliverablesServer",
    "ProjectExportServer",
    "OCIResourceManagerServer",
    "DeploymentMonitorServer",
]
