"""
Phase 5: Implementation - Agent nodes for code generation and deployment preparation.

This phase generates Terraform code, validates it, and prepares for deployment.
"""

import os
import json
import time
from typing import Dict, Any, List
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# MCP server — Terraform code generation
from src.mcp_servers.terraform_gen_server import terraform_gen_server

from src.models.state_schema import (
    MigrationState,
    PhaseStatus,
    ImplementationStrategy,
    TerraformModule,
    GeneratedCode
)
from src.utils.oci_genai import get_llm
from src.utils.config import config
from src.utils.logger import logger, log_node_entry, log_node_exit, log_mcp_call, log_llm_call, log_error


# Phase 5 Node 1: Strategy Selection
def strategy_selection(state: MigrationState) -> MigrationState:
    """
    Select implementation strategy based on complexity and requirements.
    
    Strategies:
    1. Pre-packaged: Use OCI pre-built templates
    2. Dynamic Terraform: Generate custom Terraform code
    3. Third-party: Use external frameworks (Ansible, Pulumi)
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with selected strategy
    """
    try:
        t0 = time.time()
        num_components = len(state.design.architecture_components)
        has_custom_config = any(
            len(c.configuration) > 5
            for c in state.design.architecture_components
        )
        log_node_entry(state.migration_id, "implementation", "strategy_selection", {
            "component_count": num_components,
            "has_custom_config": has_custom_config,
        })

        state.current_phase = "implementation"
        state.phase_status = PhaseStatus.IN_PROGRESS

        # Strategy selection logic
        if num_components <= 5 and not has_custom_config:
            strategy = ImplementationStrategy.PRE_PACKAGED
            reason = "simple architecture (≤5 components, no custom config)"
        elif num_components > 20 or has_custom_config:
            strategy = ImplementationStrategy.DYNAMIC_TERRAFORM
            reason = "complex architecture (>20 components or custom config)"
        else:
            strategy = ImplementationStrategy.DYNAMIC_TERRAFORM
            reason = "default"

        state.implementation.strategy = strategy
        state.messages.append({
            "role": "system",
            "content": f"Implementation strategy: {strategy.value}"
        })

        log_node_exit(state.migration_id, "implementation", "strategy_selection", {
            "strategy": strategy.value,
            "reason": reason,
            "component_count": num_components,
        }, duration_ms=(time.time() - t0) * 1000)

        return state

    except Exception as e:
        log_error(state.migration_id, "strategy_selection_error", str(e), phase="implementation")
        state.errors.append(f"Strategy selection error: {str(e)}")
        return state


# Phase 5 Node 2: Terraform Module Definition
def terraform_module_definition(state: MigrationState) -> MigrationState:
    """
    Define Terraform modules for the architecture.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with Terraform modules
    """
    try:
        t0 = time.time()
        log_node_entry(state.migration_id, "implementation", "terraform_module_definition", {
            "strategy": state.implementation.strategy.value if state.implementation.strategy else "unknown",
        })

        # Define standard modules
        modules = [
            TerraformModule(
                module_name="network",
                source="oracle-terraform-modules/vcn/oci",
                version="3.5.3",
                variables={
                    "compartment_id": "var.compartment_id",
                    "vcn_name": "migration-vcn",
                    "vcn_dns_label": "migrationvcn",
                    "vcn_cidrs": ["10.0.0.0/16"]
                }
            ),
            TerraformModule(
                module_name="compute",
                source="oracle-terraform-modules/compute-instance/oci",
                version="2.4.1",
                variables={
                    "compartment_id": "var.compartment_id",
                    "availability_domain": "var.availability_domain",
                    "shape": "VM.Standard.E4.Flex",
                    "instance_count": 1
                }
            ),
            TerraformModule(
                module_name="database",
                source="oracle-terraform-modules/autonomous-database/oci",
                version="1.0.1",
                variables={
                    "compartment_id": "var.compartment_id",
                    "db_name": "migrationdb",
                    "cpu_core_count": 2,
                    "data_storage_size_in_tbs": 1
                }
            ),
            TerraformModule(
                module_name="load_balancer",
                source="oracle-terraform-modules/load-balancer/oci",
                version="2.0.1",
                variables={
                    "compartment_id": "var.compartment_id",
                    "shape": "flexible",
                    "subnet_ids": ["module.network.subnet_ids"]
                }
            ),
            TerraformModule(
                module_name="object_storage",
                source="oracle-terraform-modules/object-storage/oci",
                version="1.0.0",
                variables={
                    "compartment_id": "var.compartment_id",
                    "bucket_name": "migration-data",
                    "namespace": "var.object_storage_namespace"
                }
            )
        ]
        
        state.implementation.terraform_modules = modules

        module_names = [m.module_name for m in modules]
        log_node_exit(state.migration_id, "implementation", "terraform_module_definition", {
            "modules_defined": len(modules),
            "module_names": str(module_names),
        }, duration_ms=(time.time() - t0) * 1000)

        return state

    except Exception as e:
        log_error(state.migration_id, "terraform_module_def_error", str(e), phase="implementation")
        state.errors.append(f"Module definition error: {str(e)}")
        return state


# Phase 5 Node 3: Terraform Code Generation
def terraform_code_generation(state: MigrationState) -> MigrationState:
    """
    Generate Terraform code using terraform_gen_server MCP tool.

    Strategy:
      1. Call terraform_gen_server.generate_three_tier_project() to get a
         complete, validated set of .tf files (provider, variables, network,
         security, compute, database, load_balancer, outputs).
      2. Append terraform.tfvars with migration-specific values.
      3. Use LLM only for components that have a unique OCI service not covered
         by the standard three-tier template (e.g. OKE, Functions, Streaming).
    """
    try:
        t0 = time.time()
        region = getattr(state, "target_region", None) or "us-ashburn-1"
        project_name = f"migration-{state.migration_id[:8]}"
        log_node_entry(state.migration_id, "implementation", "terraform_code_generation", {
            "project_name": project_name,
            "region": region,
            "components": len(state.design.architecture_components),
            "modules": len(state.implementation.terraform_modules),
        })

        # ── Step 1: MCP-generated base project ───────────────────────────────
        t_mcp = time.time()
        project = terraform_gen_server.generate_three_tier_project(
            project_name=project_name,
            region=region,
        )
        mcp_ms = (time.time() - t_mcp) * 1000
        log_mcp_call(
            state.migration_id,
            "terraform_gen_server",
            "generate_three_tier_project",
            inputs={"project_name": project_name, "region": region},
            result={
                "files_generated": len(project.get("files", {})),
                "file_names": str(list(project.get("files", {}).keys())),
            },
            duration_ms=mcp_ms,
        )

        # Determine module_type for each standard file
        _file_module_map = {
            "provider.tf": "provider",
            "variables.tf": "variables",
            "outputs.tf": "outputs",
            "network.tf": "resource",
            "security.tf": "resource",
            "compute.tf": "resource",
            "database.tf": "resource",
            "load_balancer.tf": "resource",
        }

        for fname, content in project.get("files", {}).items():
            state.implementation.generated_code.append(GeneratedCode(
                file_path=fname,
                content=content,
                module_type=_file_module_map.get(fname, "resource"),
                validated=False,
            ))

        # ── Step 2: terraform.tfvars with real migration values ───────────────
        tfvars = generate_tfvars(state)
        state.implementation.generated_code.append(GeneratedCode(
            file_path="terraform.tfvars",
            content=tfvars,
            module_type="variables",
            validated=False,
        ))

        # ── Step 3: Extra resources for non-standard components (LLM) ─────────
        standard_services = {
            "Compute", "Load Balancer", "VCN", "Subnet",
            "Internet Gateway", "NAT Gateway", "Autonomous Database",
            "Object Storage", "Security List", "Network Security Group",
        }
        extra_components = [
            c for c in state.design.architecture_components
            if c.oci_service and c.oci_service not in standard_services
        ]

        if extra_components:
            llm = get_llm()
            for component in extra_components[:3]:  # cap at 3 to avoid latency
                # Try MCP resource template first; fall back to LLM
                oci_resource_type = component.configuration.get("terraform_resource", "")
                if oci_resource_type:
                    t_res = time.time()
                    resource_result = terraform_gen_server.generate_resource(
                        resource_type=oci_resource_type,
                        resource_name=component.component_id,
                        params=component.configuration,
                    )
                    log_mcp_call(
                        state.migration_id,
                        "terraform_gen_server",
                        "generate_resource",
                        inputs={
                            "resource_type": oci_resource_type,
                            "resource_name": component.component_id,
                        },
                        result={
                            "template_found": resource_result.get("template_found", False),
                            "content_chars": len(resource_result.get("content", "")),
                        },
                        duration_ms=(time.time() - t_res) * 1000,
                    )
                    if resource_result.get("template_found"):
                        state.implementation.generated_code.append(GeneratedCode(
                            file_path=f"{component.component_id}.tf",
                            content=resource_result["content"],
                            module_type="resource",
                            validated=False,
                        ))
                        continue

                # LLM fallback for truly custom components
                t_llm = time.time()
                component_tf = generate_component_tf(state, component, llm)
                log_llm_call(
                    state.migration_id,
                    "terraform_code_generation",
                    prompt_preview=(
                        f"component={component.name}, type={component.component_type}, "
                        f"service={component.oci_service}"
                    ),
                    response_preview=f"tf_chars={len(component_tf)}, file={component.component_id}.tf",
                    duration_ms=(time.time() - t_llm) * 1000,
                )
                state.implementation.generated_code.append(GeneratedCode(
                    file_path=f"{component.component_id}.tf",
                    content=component_tf,
                    module_type="resource",
                    validated=False,
                ))

        log_node_exit(state.migration_id, "implementation", "terraform_code_generation", {
            "total_files_generated": len(state.implementation.generated_code),
            "mcp_base_files": len(project.get("files", {})),
            "extra_components": len(extra_components),
            "file_names": str([c.file_path for c in state.implementation.generated_code]),
        }, duration_ms=(time.time() - t0) * 1000)
        return state

    except Exception as e:
        log_error(state.migration_id, "terraform_codegen_error", str(e), phase="implementation")
        state.errors.append(f"Code generation error: {str(e)}")
        return state


def generate_main_tf(state: MigrationState, llm) -> str:
    """Generate main.tf file"""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Generate a Terraform main.tf file for OCI migration.
        
        Include:
        1. Required providers and versions
        2. Module declarations
        3. Resource dependencies
        4. Data sources
        
        Use OCI Terraform provider v5.0+
        Follow Terraform best practices
        Include comments for clarity
        """),
        ("user", """Components: {components}
        Modules: {modules}""")
    ])
    
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({
        "components": str([c.dict() for c in state.design.architecture_components]),
        "modules": str([m.dict() for m in state.implementation.terraform_modules])
    })


def generate_variables_tf(state: MigrationState, llm) -> str:
    """Generate variables.tf file"""
    
    variables = """# Variables for OCI Migration
# Auto-generated by Cloud Migration Agent

variable "tenancy_ocid" {
  description = "OCI Tenancy OCID"
  type        = string
}

variable "user_ocid" {
  description = "OCI User OCID"
  type        = string
}

variable "fingerprint" {
  description = "OCI API Key Fingerprint"
  type        = string
}

variable "private_key_path" {
  description = "Path to OCI API Private Key"
  type        = string
}

variable "region" {
  description = "OCI Region"
  type        = string
  default     = "us-ashburn-1"
}

variable "compartment_id" {
  description = "OCI Compartment OCID"
  type        = string
}

variable "availability_domain" {
  description = "Availability Domain"
  type        = string
}

variable "ssh_public_key" {
  description = "SSH Public Key for compute instances"
  type        = string
}

# VCN Variables
variable "vcn_cidr_block" {
  description = "VCN CIDR Block"
  type        = string
  default     = "10.0.0.0/16"
}

# Compute Variables
variable "compute_shape" {
  description = "Compute Instance Shape"
  type        = string
  default     = "VM.Standard.E4.Flex"
}

variable "compute_ocpus" {
  description = "Number of OCPUs"
  type        = number
  default     = 2
}

variable "compute_memory_gb" {
  description = "Memory in GB"
  type        = number
  default     = 16
}

# Database Variables
variable "database_admin_password" {
  description = "Database Admin Password"
  type        = string
  sensitive   = true
}

variable "database_cpu_core_count" {
  description = "Database CPU Core Count"
  type        = number
  default     = 2
}
"""
    
    return variables


def generate_outputs_tf(state: MigrationState, llm) -> str:
    """Generate outputs.tf file"""
    
    outputs = """# Outputs for OCI Migration
# Auto-generated by Cloud Migration Agent

output "vcn_id" {
  description = "VCN OCID"
  value       = module.network.vcn_id
}

output "public_subnet_ids" {
  description = "Public Subnet OCIDs"
  value       = module.network.public_subnet_ids
}

output "private_subnet_ids" {
  description = "Private Subnet OCIDs"
  value       = module.network.private_subnet_ids
}

output "compute_instance_ids" {
  description = "Compute Instance OCIDs"
  value       = module.compute.instance_ids
}

output "compute_public_ips" {
  description = "Compute Instance Public IPs"
  value       = module.compute.public_ips
}

output "load_balancer_id" {
  description = "Load Balancer OCID"
  value       = module.load_balancer.load_balancer_id
}

output "load_balancer_ip" {
  description = "Load Balancer Public IP"
  value       = module.load_balancer.ip_address
}

output "database_id" {
  description = "Autonomous Database OCID"
  value       = module.database.autonomous_database_id
}

output "database_connection_string" {
  description = "Database Connection String"
  value       = module.database.connection_string
  sensitive   = true
}

output "object_storage_bucket" {
  description = "Object Storage Bucket Name"
  value       = module.object_storage.bucket_name
}
"""
    
    return outputs


def generate_provider_tf(state: MigrationState) -> str:
    """Generate provider.tf file"""
    
    provider = f"""# OCI Provider Configuration
# Auto-generated by Cloud Migration Agent

terraform {{
  required_version = ">= 1.0"
  
  required_providers {{
    oci = {{
      source  = "oracle/oci"
      version = "~> 5.0"
    }}
  }}
}}

provider "oci" {{
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}}
"""
    
    return provider


def generate_tfvars(state: MigrationState) -> str:
    """Generate terraform.tfvars file"""
    
    tfvars = f"""# Terraform Variables
# Auto-generated by Cloud Migration Agent
# IMPORTANT: Update these values before applying

# OCI Authentication
tenancy_ocid     = "YOUR_TENANCY_OCID"
user_ocid        = "YOUR_USER_OCID"
fingerprint      = "YOUR_FINGERPRINT"
private_key_path = "~/.oci/oci_api_key.pem"

# Target Region
region = "{state.target_region}"

# Compartment
compartment_id = "YOUR_COMPARTMENT_OCID"

# Availability Domain
availability_domain = "YOUR_AD_NAME"

# SSH Key
ssh_public_key = "YOUR_SSH_PUBLIC_KEY"

# Network Configuration
vcn_cidr_block = "10.0.0.0/16"

# Compute Configuration
compute_shape     = "VM.Standard.E4.Flex"
compute_ocpus     = 2
compute_memory_gb = 16

# Database Configuration
database_admin_password  = "YOUR_SECURE_PASSWORD"
database_cpu_core_count = 2
"""
    
    return tfvars


def generate_component_tf(state: MigrationState, component, llm) -> str:
    """Generate component-specific Terraform file"""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Generate Terraform code for a specific OCI component.
        
        Include:
        1. Resource declaration
        2. Required attributes
        3. Dependencies
        4. Tags and labels
        
        Use proper HCL syntax and OCI provider documentation.
        """),
        ("user", """Component: {component}
        Type: {type}
        OCI Service: {service}
        Configuration: {config}""")
    ])
    
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({
        "component": component.name,
        "type": component.component_type,
        "service": component.oci_service,
        "config": json.dumps(component.configuration, indent=2)
    })


# Phase 5 Node 4: Code Validation
def code_validation(state: MigrationState) -> MigrationState:
    """
    Validate generated Terraform code.
    
    Checks:
    - Syntax validity
    - Required variables defined
    - Resource naming conventions
    - Security best practices
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with validation results
    """
    try:
        t0 = time.time()
        log_node_entry(state.migration_id, "implementation", "code_validation", {
            "files_to_validate": len(state.implementation.generated_code),
        })

        all_valid = True

        for code in state.implementation.generated_code:
            # Basic validation checks
            validation_errors = []
            
            # Check for common issues
            if not code.content or len(code.content) < 10:
                validation_errors.append("Code content is empty or too short")
            
            if "variable" in code.file_path and "variable " not in code.content:
                validation_errors.append("Variables file missing variable declarations")
            
            if "provider.tf" in code.file_path and "provider " not in code.content:
                validation_errors.append("Provider file missing provider configuration")
            
            # Check for sensitive data exposure
            sensitive_patterns = ["password", "secret", "key", "token"]
            for pattern in sensitive_patterns:
                if pattern in code.content.lower() and "var." not in code.content:
                    validation_errors.append(f"Potential sensitive data exposure: {pattern}")
            
            # Update validation status
            if validation_errors:
                code.validated = False
                code.validation_errors = validation_errors
                all_valid = False
                logger.warning(f"Validation issues in {code.file_path}: {validation_errors}")
            else:
                code.validated = True
                code.validation_errors = []
        
        state.implementation.code_validated = all_valid

        invalid_files = [c.file_path for c in state.implementation.generated_code if not c.validated]
        log_node_exit(state.migration_id, "implementation", "code_validation", {
            "files_validated": len(state.implementation.generated_code),
            "all_valid": all_valid,
            "invalid_files": str(invalid_files),
        }, duration_ms=(time.time() - t0) * 1000)

        return state

    except Exception as e:
        log_error(state.migration_id, "code_validation_error", str(e), phase="implementation")
        state.errors.append(f"Code validation error: {str(e)}")
        return state


# Phase 5 Node 5: Project Export
def project_export(state: MigrationState) -> MigrationState:
    """
    Export Terraform project for external modification.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with export path
    """
    try:
        t0 = time.time()
        log_node_entry(state.migration_id, "implementation", "project_export", {
            "files_to_export": len(state.implementation.generated_code),
            "code_validated": state.implementation.code_validated,
        })

        # Create export directory
        export_dir = Path(config.app.export_dir) / state.migration_id
        export_dir.mkdir(parents=True, exist_ok=True)
        
        # Write all Terraform files
        for code in state.implementation.generated_code:
            file_path = export_dir / code.file_path
            file_path.write_text(code.content)
            logger.debug(f"Exported {code.file_path}")
        
        # Create README
        readme_content = f"""# OCI Migration Project: {state.migration_id}

## Overview
This Terraform project was auto-generated by the Cloud Migration Agent.

## Components
- {len(state.design.architecture_components)} architecture components
- {len(state.implementation.generated_code)} Terraform files
- Target region: {state.target_region}

## Usage

1. Update `terraform.tfvars` with your OCI credentials
2. Initialize Terraform: `terraform init`
3. Review plan: `terraform plan`
4. Apply configuration: `terraform apply`

## Files
{chr(10).join(f"- {code.file_path}" for code in state.implementation.generated_code)}

## Generated
{state.created_at.isoformat()}
"""
        
        readme_path = export_dir / "README.md"
        readme_path.write_text(readme_content)
        
        state.implementation.project_exported = True
        state.implementation.export_path = str(export_dir)

        log_node_exit(state.migration_id, "implementation", "project_export", {
            "export_path": str(export_dir),
            "files_written": len(state.implementation.generated_code),
            "readme_written": True,
        }, duration_ms=(time.time() - t0) * 1000)

        return state

    except Exception as e:
        log_error(state.migration_id, "project_export_error", str(e), phase="implementation")
        state.errors.append(f"Project export error: {str(e)}")
        return state


# ========== PATHWAY A: PRE-PACKAGED COMPONENTS ==========

# OCI pre-packaged component templates
OCI_COMPONENT_CATALOG = [
    {
        "component_id": "landing-zone-v2",
        "name": "OCI Landing Zone",
        "description": "Secure, scalable OCI foundation with compartments, policies, VCN, and security controls",
        "category": "Foundation",
        "complexity": "medium",
        "terraform_source": "oracle-quickstart/oci-landing-zones",
        "parameters": ["compartment_ocid", "tenancy_ocid", "region", "enable_cloud_guard", "enable_vulnerability_scanning"]
    },
    {
        "component_id": "three-tier-web-app",
        "name": "Three-Tier Web Application",
        "description": "Load-balanced web application with Compute, private database subnet",
        "category": "Web Application",
        "complexity": "low",
        "terraform_source": "oracle-quickstart/oci-arch-web-app-mds",
        "parameters": ["compartment_ocid", "vcn_cidr", "compute_shape", "db_admin_password"]
    },
    {
        "component_id": "microservices-oke",
        "name": "Microservices on OKE",
        "description": "Kubernetes-based microservices architecture with OKE and API Gateway",
        "category": "Kubernetes",
        "complexity": "high",
        "terraform_source": "oracle-quickstart/oci-arch-microservices",
        "parameters": ["compartment_ocid", "cluster_name", "node_pool_size", "node_shape"]
    },
    {
        "component_id": "data-platform",
        "name": "OCI Data Platform",
        "description": "Modern data platform with ADW, Data Integration, and OAC",
        "category": "Data & Analytics",
        "complexity": "medium",
        "terraform_source": "oracle-quickstart/oci-arch-data-platform",
        "parameters": ["compartment_ocid", "adw_ocpus", "adw_storage_tb", "oac_capacity"]
    }
]


def component_selection(state: MigrationState) -> MigrationState:
    """
    Pathway A: Browse and select pre-packaged OCI components.

    Selects the best pre-packaged component template based on the
    architecture design from previous phases.

    Args:
        state: Current migration state

    Returns:
        Updated state with selected component
    """
    try:
        logger.info(f"Selecting pre-packaged component for migration {state.migration_id}")

        state.current_phase = "implementation"
        state.phase_status = PhaseStatus.IN_PROGRESS

        # Use LLM to select best component based on design
        llm = get_llm()
        prompt = ChatPromptTemplate.from_template("""
You are an OCI migration expert. Based on the migration context, select the best pre-packaged component.

Migration Context: {user_context}
Source Provider: {source_provider}
Target Region: {target_region}
Design Components: {components}

Available Components:
{catalog}

Select the most appropriate component template. Return a JSON object with:
{{
    "selected_component_id": "component_id",
    "reasoning": "why this component was selected",
    "match_score": 0.0-1.0,
    "customization_needed": ["list of customizations"]
}}
""")

        chain = prompt | llm | StrOutputParser()
        components_summary = [
            f"- {c.name} ({c.oci_service or c.component_type})"
            for c in state.design.architecture_components[:5]
        ]
        catalog_summary = "\n".join([
            f"- {c['component_id']}: {c['name']} - {c['description']}"
            for c in OCI_COMPONENT_CATALOG
        ])

        result = chain.invoke({
            "user_context": state.user_context[:500],
            "source_provider": state.source_provider,
            "target_region": state.target_region,
            "components": "\n".join(components_summary),
            "catalog": catalog_summary
        })

        # Parse result
        try:
            import re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                selection = json.loads(json_match.group())
            else:
                selection = {"selected_component_id": "three-tier-web-app", "reasoning": "Default selection", "match_score": 0.70}
        except Exception:
            selection = {"selected_component_id": "three-tier-web-app", "reasoning": "Default selection", "match_score": 0.70}

        # Find selected component details
        component_id = selection.get("selected_component_id", "three-tier-web-app")
        selected = next((c for c in OCI_COMPONENT_CATALOG if c["component_id"] == component_id), OCI_COMPONENT_CATALOG[1])

        state.implementation.selected_component = {
            **selected,
            "selection_reasoning": selection.get("reasoning", ""),
            "match_score": selection.get("match_score", 0.70),
            "customization_needed": selection.get("customization_needed", [])
        }

        state.messages.append({
            "role": "system",
            "content": f"Selected pre-packaged component: {selected['name']} (score: {selection.get('match_score', 0.70):.2f})"
        })

        logger.info(f"Selected component: {selected['name']}")
        return state

    except Exception as e:
        logger.error(f"Component selection failed: {str(e)}")
        state.errors.append(f"Component selection error: {str(e)}")
        # Fallback to default
        state.implementation.selected_component = OCI_COMPONENT_CATALOG[1]
        return state


def component_configuration(state: MigrationState) -> MigrationState:
    """
    Pathway A: Configure parameters for selected pre-packaged component.

    Args:
        state: Current migration state

    Returns:
        Updated state with configured component parameters
    """
    try:
        logger.info(f"Configuring component parameters for migration {state.migration_id}")

        selected = state.implementation.selected_component
        if not selected:
            state.errors.append("No component selected for configuration")
            return state

        # Generate configuration based on design
        llm = get_llm()
        prompt = ChatPromptTemplate.from_template("""
Configure the OCI component parameters for the migration.

Component: {component_name}
Component ID: {component_id}
Required Parameters: {parameters}

Migration Details:
- Source: {source_provider}
- Target Region: {target_region}
- User Context: {user_context}

Generate a terraform.tfvars JSON configuration. Return:
{{
    "configured_parameters": {{
        "param_name": "param_value",
        ...
    }},
    "configuration_notes": "any important notes"
}}
""")

        chain = prompt | llm | StrOutputParser()
        result = chain.invoke({
            "component_name": selected.get("name", ""),
            "component_id": selected.get("component_id", ""),
            "parameters": json.dumps(selected.get("parameters", [])),
            "source_provider": state.source_provider,
            "target_region": state.target_region,
            "user_context": state.user_context[:300]
        })

        # Parse configuration
        try:
            import re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            config_data = json.loads(json_match.group()) if json_match else {}
        except Exception:
            config_data = {}

        # Default configuration
        default_config = {
            "region": state.target_region,
            "compartment_ocid": "var.compartment_ocid",
            "tenancy_ocid": "var.tenancy_ocid",
            "vcn_cidr": "10.0.0.0/16",
            "enable_cloud_guard": True,
            "enable_vulnerability_scanning": True
        }
        configured_params = {**default_config, **config_data.get("configured_parameters", {})}

        # Update selected component with configuration
        state.implementation.selected_component = {
            **selected,
            "configured_parameters": configured_params,
            "configuration_notes": config_data.get("configuration_notes", ""),
            "terraform_tfvars": json.dumps(configured_params, indent=2)
        }

        state.messages.append({
            "role": "system",
            "content": f"Component {selected.get('name')} configured with {len(configured_params)} parameters"
        })

        logger.info(f"Component configured successfully")
        return state

    except Exception as e:
        logger.error(f"Component configuration failed: {str(e)}")
        state.errors.append(f"Component configuration error: {str(e)}")
        return state


# ========== PATHWAY B: PROJECT IMPORT (export/import loop) ==========

def project_import(state: MigrationState) -> MigrationState:
    """
    Pathway B: Import a user-modified Terraform project.

    Handles the re-import after the user has modified the exported project.

    Args:
        state: Current migration state

    Returns:
        Updated state with imported project
    """
    try:
        logger.info(f"Importing modified project for migration {state.migration_id}")

        import_path = state.implementation.import_path or state.implementation.export_path

        if not import_path:
            # If no path set, simulate import from export location
            import_path = str(Path(config.app.export_dir) / state.migration_id)

        # Read imported Terraform files
        import_dir = Path(import_path)
        imported_files = []

        if import_dir.exists():
            for tf_file in import_dir.glob("*.tf"):
                try:
                    content = tf_file.read_text()
                    imported_files.append(GeneratedCode(
                        file_path=tf_file.name,
                        content=content,
                        module_type="imported",
                        validated=False
                    ))
                except Exception as e:
                    logger.warning(f"Could not read {tf_file}: {e}")
        else:
            # Use existing generated code as fallback
            imported_files = state.implementation.generated_code

        state.implementation.generated_code = imported_files
        state.implementation.import_path = str(import_dir)

        state.messages.append({
            "role": "system",
            "content": f"Imported {len(imported_files)} Terraform files from {import_path}"
        })

        logger.info(f"Imported {len(imported_files)} files from {import_path}")
        return state

    except Exception as e:
        logger.error(f"Project import failed: {str(e)}")
        state.errors.append(f"Project import error: {str(e)}")
        return state


def import_validation(state: MigrationState) -> MigrationState:
    """
    Pathway B: Validate the re-imported Terraform project.

    Args:
        state: Current migration state

    Returns:
        Updated state with import validation results
    """
    try:
        logger.info(f"Validating imported project for migration {state.migration_id}")

        validation_errors = []
        validation_warnings = []
        files_validated = 0

        for code in state.implementation.generated_code:
            content = code.content

            # Check for required provider block
            if code.file_path == "provider.tf":
                if "required_providers" not in content:
                    validation_warnings.append(f"{code.file_path}: Missing required_providers block")
                if "oracle/oci" not in content:
                    validation_errors.append(f"{code.file_path}: Missing OCI provider configuration")

            # Check for security issues
            if "0.0.0.0/0" in content and "ingress" in content.lower():
                validation_warnings.append(f"{code.file_path}: Open ingress rule detected (0.0.0.0/0) - review security")

            # Check HCL syntax basics
            open_braces = content.count("{")
            close_braces = content.count("}")
            if open_braces != close_braces:
                validation_errors.append(f"{code.file_path}: Unbalanced braces ({open_braces} open, {close_braces} close)")

            code.validated = len(validation_errors) == 0
            code.validation_errors = [e for e in validation_errors if code.file_path in e]
            files_validated += 1

        state.implementation.code_validated = len(validation_errors) == 0
        state.implementation.import_validated = True

        state.messages.append({
            "role": "system",
            "content": f"Import validation: {files_validated} files, {len(validation_errors)} errors, {len(validation_warnings)} warnings"
        })

        if validation_errors:
            state.errors.extend(validation_errors[:3])

        logger.info(f"Import validation complete: {'PASS' if len(validation_errors) == 0 else 'FAIL'}")
        return state

    except Exception as e:
        logger.error(f"Import validation failed: {str(e)}")
        state.errors.append(f"Import validation error: {str(e)}")
        return state


# ========== PATHWAY C: THIRD-PARTY FRAMEWORKS ==========

SUPPORTED_FRAMEWORKS = [
    {
        "framework_id": "pulumi",
        "name": "Pulumi",
        "description": "Infrastructure as code using Python, TypeScript, Go, or .NET",
        "languages": ["python", "typescript", "go", "dotnet"],
        "oci_provider": "pulumi/oci",
        "install_cmd": "pip install pulumi pulumi-oci"
    },
    {
        "framework_id": "ansible",
        "name": "Ansible",
        "description": "Agentless automation platform using YAML playbooks",
        "languages": ["yaml"],
        "oci_provider": "oracle.oci.oci",
        "install_cmd": "pip install ansible oci"
    },
    {
        "framework_id": "terraform-cdk",
        "name": "Terraform CDK (CDKTF)",
        "description": "Define Terraform configurations using Python or TypeScript",
        "languages": ["python", "typescript"],
        "oci_provider": "oracle/oci",
        "install_cmd": "npm install -g cdktf-cli && pip install cdktf cdktf-cdktf-provider-oci"
    },
    {
        "framework_id": "crossplane",
        "name": "Crossplane",
        "description": "Kubernetes-native infrastructure provisioning",
        "languages": ["yaml"],
        "oci_provider": "crossplane-contrib/provider-oci",
        "install_cmd": "helm install crossplane crossplane-stable/crossplane"
    }
]


def framework_selection(state: MigrationState) -> MigrationState:
    """
    Pathway C: Select a third-party IaC framework.

    Args:
        state: Current migration state

    Returns:
        Updated state with selected framework
    """
    try:
        logger.info(f"Selecting third-party framework for migration {state.migration_id}")

        state.current_phase = "implementation"
        state.phase_status = PhaseStatus.IN_PROGRESS

        # Use LLM to select framework
        llm = get_llm()
        prompt = ChatPromptTemplate.from_template("""
Select the best third-party IaC framework for this migration.

Migration Context: {user_context}
Architecture Complexity: {complexity}
Team Preferences: {preferences}

Available Frameworks:
{frameworks}

Consider: existing team expertise, complexity, integration requirements.
Return JSON:
{{
    "selected_framework_id": "framework_id",
    "reasoning": "explanation",
    "language": "preferred language",
    "confidence": 0.0-1.0
}}
""")

        chain = prompt | llm | StrOutputParser()
        num_components = len(state.design.architecture_components)
        complexity = "high" if num_components > 20 else "medium" if num_components > 10 else "low"

        frameworks_summary = "\n".join([
            f"- {f['framework_id']}: {f['name']} - {f['description']}"
            for f in SUPPORTED_FRAMEWORKS
        ])

        result = chain.invoke({
            "user_context": state.user_context[:400],
            "complexity": complexity,
            "preferences": "standard enterprise tools preferred",
            "frameworks": frameworks_summary
        })

        try:
            import re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            selection = json.loads(json_match.group()) if json_match else {}
        except Exception:
            selection = {}

        framework_id = selection.get("selected_framework_id", "pulumi")
        selected = next((f for f in SUPPORTED_FRAMEWORKS if f["framework_id"] == framework_id), SUPPORTED_FRAMEWORKS[0])

        state.implementation.framework_artifacts = {
            **selected,
            "selection_reasoning": selection.get("reasoning", "Selected based on migration requirements"),
            "preferred_language": selection.get("language", "python"),
            "confidence": selection.get("confidence", 0.75),
            "status": "framework_selected"
        }

        state.messages.append({
            "role": "system",
            "content": f"Selected framework: {selected['name']} ({selected['framework_id']})"
        })

        logger.info(f"Selected framework: {selected['name']}")
        return state

    except Exception as e:
        logger.error(f"Framework selection failed: {str(e)}")
        state.errors.append(f"Framework selection error: {str(e)}")
        state.implementation.framework_artifacts = SUPPORTED_FRAMEWORKS[0]
        return state


def framework_configuration(state: MigrationState) -> MigrationState:
    """
    Pathway C: Configure the selected third-party framework.

    Generates framework-specific configuration files and boilerplate.

    Args:
        state: Current migration state

    Returns:
        Updated state with framework configuration
    """
    try:
        logger.info(f"Configuring framework for migration {state.migration_id}")

        framework = state.implementation.framework_artifacts
        if not framework:
            state.errors.append("No framework selected for configuration")
            return state

        framework_id = framework.get("framework_id", "pulumi")

        # Generate framework-specific boilerplate
        if framework_id == "pulumi":
            config_files = {
                "Pulumi.yaml": f"""name: oci-migration-{state.migration_id[:8]}
description: OCI migration generated by Cloud Migration Agent
runtime: python
config:
  oci:region:
    value: {state.target_region}
""",
                "__main__.py": f"""\"\"\"OCI Migration - Generated by Cloud Migration Agent\"\"\"\nimport pulumi\nimport pulumi_oci as oci\n\n# VCN\nvcn = oci.core.Vcn(\n    "migration-vcn",\n    cidr_block="10.0.0.0/16",\n    compartment_id=pulumi.Config("oci").require("compartment_id"),\n    display_name="migration-vcn"\n)\n\npulumi.export("vcn_id", vcn.id)\n""",
                "requirements.txt": "pulumi>=3.0.0\npulumi-oci>=1.0.0\n"
            }
        elif framework_id == "ansible":
            config_files = {
                "site.yml": f"""---\n- name: OCI Migration\n  hosts: localhost\n  connection: local\n  gather_facts: no\n  vars:\n    region: {state.target_region}\n    compartment_id: "{{ compartment_id }}"\n  tasks:\n    - name: Create VCN\n      oracle.oci.oci_network_vcn:\n        compartment_id: "{{{{ compartment_id }}}}"\n        cidr_block: "10.0.0.0/16"\n        display_name: "migration-vcn"\n      register: vcn_result\n""",
                "inventory.ini": "[localhost]\nlocalhost ansible_connection=local\n",
                "requirements.yml": "---\ncollections:\n  - name: oracle.oci\n"
            }
        else:
            config_files = {
                "README.md": f"# OCI Migration - {framework.get('name', 'Framework')}\n\nGenerated by Cloud Migration Agent.\n\nFramework: {framework_id}\nRegion: {state.target_region}\n"
            }

        state.implementation.framework_artifacts = {
            **framework,
            "config_files": config_files,
            "install_cmd": framework.get("install_cmd", ""),
            "status": "framework_configured",
            "file_count": len(config_files)
        }

        state.messages.append({
            "role": "system",
            "content": f"Framework {framework_id} configured with {len(config_files)} files"
        })

        logger.info(f"Framework configured: {len(config_files)} files generated")
        return state

    except Exception as e:
        logger.error(f"Framework configuration failed: {str(e)}")
        state.errors.append(f"Framework configuration error: {str(e)}")
        return state


# ========== CONVERGENCE: IMPLEMENTATION REVIEW GATE PREP ==========

def prepare_implementation_review(state: MigrationState) -> MigrationState:
    """
    Convergence point: Prepare state for implementation review gate.

    Called after any pathway (A, B, or C) completes to consolidate
    artifacts before the final implementation review.

    Args:
        state: Current migration state

    Returns:
        Updated state ready for implementation review
    """
    try:
        t0 = time.time()
        log_node_entry(state.migration_id, "implementation", "prepare_implementation_review", {
            "strategy": state.implementation.strategy.value if state.implementation.strategy else "unknown",
            "code_validated": state.implementation.code_validated,
            "project_exported": state.implementation.project_exported,
        })

        strategy = state.implementation.strategy

        summary_parts = [f"Implementation via {strategy.value if strategy else 'unknown'} pathway."]

        if strategy == ImplementationStrategy.PRE_PACKAGED:
            comp = state.implementation.selected_component
            if comp:
                summary_parts.append(f"Pre-packaged: {comp.get('name', 'N/A')}")
                summary_parts.append(f"Source: {comp.get('terraform_source', 'N/A')}")

        elif strategy == ImplementationStrategy.DYNAMIC_TERRAFORM:
            num_files = len(state.implementation.generated_code)
            validated = state.implementation.code_validated
            summary_parts.append(f"Generated {num_files} Terraform files")
            summary_parts.append(f"Validation: {'PASSED' if validated else 'FAILED'}")

        elif strategy == ImplementationStrategy.THIRD_PARTY:
            framework = state.implementation.framework_artifacts
            if framework:
                summary_parts.append(f"Framework: {framework.get('name', 'N/A')}")
                files = framework.get("config_files", {})
                summary_parts.append(f"Configuration files: {len(files)}")

        state.phase_status = PhaseStatus.WAITING_REVIEW

        summary = " | ".join(summary_parts)
        state.messages.append({"role": "system", "content": summary})

        log_node_exit(state.migration_id, "implementation", "prepare_implementation_review", {
            "phase_status": "WAITING_REVIEW",
            "summary": summary,
        }, duration_ms=(time.time() - t0) * 1000)
        return state

    except Exception as e:
        log_error(state.migration_id, "impl_review_prep_error", str(e), phase="implementation")
        state.errors.append(f"Implementation review prep error: {str(e)}")
        return state


# ========== ROUTING FUNCTIONS ==========

def route_by_strategy(state: MigrationState) -> str:
    """
    Route to the appropriate pathway based on selected strategy.

    Returns:
        "pre_packaged", "dynamic_terraform", or "third_party"
    """
    strategy = state.implementation.strategy
    if strategy == ImplementationStrategy.PRE_PACKAGED:
        return "pre_packaged"
    elif strategy == ImplementationStrategy.THIRD_PARTY:
        return "third_party"
    else:
        return "dynamic_terraform"
