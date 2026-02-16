"""
Phase 5: Implementation - Agent nodes for code generation and deployment preparation.

This phase generates Terraform code, validates it, and prepares for deployment.
"""

import os
import json
from typing import Dict, Any, List
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.models.state_schema import (
    MigrationState,
    PhaseStatus,
    ImplementationStrategy,
    TerraformModule,
    GeneratedCode
)
from src.utils.oci_genai import get_llm
from src.utils.config import config
from src.utils.logger import logger


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
        logger.info(f"Selecting implementation strategy for migration {state.migration_id}")
        
        state.current_phase = "implementation"
        state.phase_status = PhaseStatus.IN_PROGRESS
        
        # Analyze complexity
        num_components = len(state.design.architecture_components)
        has_custom_config = any(
            len(c.configuration) > 5 
            for c in state.design.architecture_components
        )
        
        # Strategy selection logic
        if num_components <= 5 and not has_custom_config:
            strategy = ImplementationStrategy.PRE_PACKAGED
            logger.info("Selected PRE_PACKAGED strategy (simple architecture)")
        elif num_components > 20 or has_custom_config:
            strategy = ImplementationStrategy.DYNAMIC_TERRAFORM
            logger.info("Selected DYNAMIC_TERRAFORM strategy (complex architecture)")
        else:
            strategy = ImplementationStrategy.DYNAMIC_TERRAFORM
            logger.info("Selected DYNAMIC_TERRAFORM strategy (default)")
        
        state.implementation.strategy = strategy
        
        state.messages.append({
            "role": "system",
            "content": f"Implementation strategy: {strategy.value}"
        })
        
        return state
        
    except Exception as e:
        logger.error(f"Strategy selection failed: {str(e)}")
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
        logger.info(f"Defining Terraform modules for migration {state.migration_id}")
        
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
        
        logger.info(f"Defined {len(modules)} Terraform modules")
        
        return state
        
    except Exception as e:
        logger.error(f"Terraform module definition failed: {str(e)}")
        state.errors.append(f"Module definition error: {str(e)}")
        return state


# Phase 5 Node 3: Terraform Code Generation
def terraform_code_generation(state: MigrationState) -> MigrationState:
    """
    Generate Terraform code for each component.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with generated Terraform code
    """
    try:
        logger.info(f"Generating Terraform code for migration {state.migration_id}")
        
        llm = get_llm()
        
        # Generate main.tf
        main_tf = generate_main_tf(state, llm)
        state.implementation.generated_code.append(GeneratedCode(
            file_path="main.tf",
            content=main_tf,
            module_type="main",
            validated=False
        ))
        
        # Generate variables.tf
        variables_tf = generate_variables_tf(state, llm)
        state.implementation.generated_code.append(GeneratedCode(
            file_path="variables.tf",
            content=variables_tf,
            module_type="variables",
            validated=False
        ))
        
        # Generate outputs.tf
        outputs_tf = generate_outputs_tf(state, llm)
        state.implementation.generated_code.append(GeneratedCode(
            file_path="outputs.tf",
            content=outputs_tf,
            module_type="outputs",
            validated=False
        ))
        
        # Generate provider.tf
        provider_tf = generate_provider_tf(state)
        state.implementation.generated_code.append(GeneratedCode(
            file_path="provider.tf",
            content=provider_tf,
            module_type="provider",
            validated=False
        ))
        
        # Generate terraform.tfvars
        tfvars = generate_tfvars(state)
        state.implementation.generated_code.append(GeneratedCode(
            file_path="terraform.tfvars",
            content=tfvars,
            module_type="variables",
            validated=False
        ))
        
        # Generate component-specific files
        for component in state.design.architecture_components[:5]:  # Top 5 for demonstration
            component_tf = generate_component_tf(state, component, llm)
            state.implementation.generated_code.append(GeneratedCode(
                file_path=f"{component.component_id}.tf",
                content=component_tf,
                module_type="resource",
                validated=False
            ))
        
        logger.info(f"Generated {len(state.implementation.generated_code)} Terraform files")
        
        return state
        
    except Exception as e:
        logger.error(f"Terraform code generation failed: {str(e)}")
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
        logger.info(f"Validating Terraform code for migration {state.migration_id}")
        
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
        
        if all_valid:
            logger.info("All Terraform code validated successfully")
        else:
            logger.warning("Some Terraform files have validation issues")
        
        return state
        
    except Exception as e:
        logger.error(f"Code validation failed: {str(e)}")
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
        logger.info(f"Exporting Terraform project for migration {state.migration_id}")
        
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
        
        logger.info(f"Project exported to: {export_dir}")
        
        return state
        
    except Exception as e:
        logger.error(f"Project export failed: {str(e)}")
        state.errors.append(f"Project export error: {str(e)}")
        return state
