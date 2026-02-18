"""MCP Server 9: OCI Terraform Code Generation.

Generates production-ready Terraform HCL for all major OCI services.
Templates conform to the official oracle/oci Terraform provider >= 5.x.

Reference: https://registry.terraform.io/providers/oracle/oci/latest/docs
"""
import textwrap
import time
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# PROVIDER + TERRAFORM BLOCK
# ---------------------------------------------------------------------------
PROVIDER_TF = textwrap.dedent("""\
    terraform {
      required_version = ">= 1.3.0"
      required_providers {
        oci = {
          source  = "oracle/oci"
          version = ">= 5.0.0"
        }
      }
    }

    provider "oci" {
      region           = var.region
      tenancy_ocid     = var.tenancy_ocid
      user_ocid        = var.user_ocid
      fingerprint      = var.fingerprint
      private_key_path = var.private_key_path
    }
""")

# ---------------------------------------------------------------------------
# VARIABLES TEMPLATE
# ---------------------------------------------------------------------------
VARIABLES_TF = textwrap.dedent("""\
    variable "tenancy_ocid" {
      description = "OCID of the OCI tenancy"
      type        = string
    }

    variable "user_ocid" {
      description = "OCID of the API-signing user"
      type        = string
    }

    variable "fingerprint" {
      description = "Fingerprint of the API signing key"
      type        = string
    }

    variable "private_key_path" {
      description = "Path to the RSA private key PEM file"
      type        = string
      default     = "~/.oci/oci_api_key.pem"
    }

    variable "region" {
      description = "OCI region identifier"
      type        = string
      default     = "us-ashburn-1"
    }

    variable "compartment_ocid" {
      description = "OCID of the target compartment"
      type        = string
    }

    variable "project_name" {
      description = "Prefix applied to all resource display names"
      type        = string
      default     = "migration"
    }

    variable "environment" {
      description = "Deployment environment (dev / staging / prod)"
      type        = string
      default     = "prod"
    }
""")

# ---------------------------------------------------------------------------
# RESOURCE TEMPLATES
# ---------------------------------------------------------------------------

_RESOURCE_TEMPLATES: Dict[str, str] = {

    # ── NETWORKING ────────────────────────────────────────────────────────────
    "oci_core_vcn": textwrap.dedent("""\
        resource "oci_core_vcn" "{name}" {{
          compartment_id = var.compartment_ocid
          display_name   = "${{var.project_name}}-vcn"
          cidr_blocks    = ["{cidr_block}"]
          dns_label      = "${{var.project_name}}"

          freeform_tags = {{
            "project"     = var.project_name
            "environment" = var.environment
          }}
        }}
    """),

    "oci_core_internet_gateway": textwrap.dedent("""\
        resource "oci_core_internet_gateway" "{name}" {{
          compartment_id = var.compartment_ocid
          vcn_id         = oci_core_vcn.{vcn_ref}.id
          display_name   = "${{var.project_name}}-igw"
          enabled        = true
        }}
    """),

    "oci_core_nat_gateway": textwrap.dedent("""\
        resource "oci_core_nat_gateway" "{name}" {{
          compartment_id = var.compartment_ocid
          vcn_id         = oci_core_vcn.{vcn_ref}.id
          display_name   = "${{var.project_name}}-natgw"
          block_traffic  = false
        }}
    """),

    "oci_core_service_gateway": textwrap.dedent("""\
        data "oci_core_services" "all_oci_services" {{
          filter {{
            name   = "name"
            values = ["All .* Services In Oracle Services Network"]
            regex  = true
          }}
        }}

        resource "oci_core_service_gateway" "{name}" {{
          compartment_id = var.compartment_ocid
          vcn_id         = oci_core_vcn.{vcn_ref}.id
          display_name   = "${{var.project_name}}-svcgw"

          services {{
            service_id = data.oci_core_services.all_oci_services.services[0].id
          }}
        }}
    """),

    "oci_core_subnet": textwrap.dedent("""\
        resource "oci_core_subnet" "{name}" {{
          compartment_id             = var.compartment_ocid
          vcn_id                     = oci_core_vcn.{vcn_ref}.id
          display_name               = "${{var.project_name}}-{subnet_type}-subnet"
          cidr_block                 = "{cidr_block}"
          dns_label                  = "{dns_label}"
          prohibit_public_ip_on_vnic = {prohibit_public_ip}
          security_list_ids          = [oci_core_security_list.{security_list_ref}.id]
          route_table_id             = oci_core_route_table.{route_table_ref}.id
        }}
    """),

    "oci_core_security_list": textwrap.dedent("""\
        resource "oci_core_security_list" "{name}" {{
          compartment_id = var.compartment_ocid
          vcn_id         = oci_core_vcn.{vcn_ref}.id
          display_name   = "${{var.project_name}}-{tier}-sl"

          # Egress: allow all
          egress_security_rules {{
            protocol    = "all"
            destination = "0.0.0.0/0"
          }}

          # Ingress: HTTPS from internet
          ingress_security_rules {{
            protocol = "6"  # TCP
            source   = "0.0.0.0/0"
            tcp_options {{
              min = 443
              max = 443
            }}
          }}

          # Ingress: HTTP (redirect)
          ingress_security_rules {{
            protocol = "6"
            source   = "0.0.0.0/0"
            tcp_options {{
              min = 80
              max = 80
            }}
          }}

          # Ingress: ICMP path discovery
          ingress_security_rules {{
            protocol = "1"
            source   = "0.0.0.0/0"
            icmp_options {{
              type = 3
              code = 4
            }}
          }}
        }}
    """),

    "oci_core_network_security_group": textwrap.dedent("""\
        resource "oci_core_network_security_group" "{name}" {{
          compartment_id = var.compartment_ocid
          vcn_id         = oci_core_vcn.{vcn_ref}.id
          display_name   = "${{var.project_name}}-{tier}-nsg"
        }}

        resource "oci_core_network_security_group_security_rule" "{name}_egress" {{
          network_security_group_id = oci_core_network_security_group.{name}.id
          direction                 = "EGRESS"
          protocol                  = "all"
          destination               = "0.0.0.0/0"
          destination_type          = "CIDR_BLOCK"
        }}

        resource "oci_core_network_security_group_security_rule" "{name}_app_ingress" {{
          network_security_group_id = oci_core_network_security_group.{name}.id
          direction                 = "INGRESS"
          protocol                  = "6"
          source                    = "{ingress_cidr}"
          source_type               = "CIDR_BLOCK"
          tcp_options {{
            destination_port_range {{
              min = {port_min}
              max = {port_max}
            }}
          }}
        }}
    """),

    "oci_core_route_table": textwrap.dedent("""\
        resource "oci_core_route_table" "{name}" {{
          compartment_id = var.compartment_ocid
          vcn_id         = oci_core_vcn.{vcn_ref}.id
          display_name   = "${{var.project_name}}-{tier}-rt"

          route_rules {{
            network_entity_id = oci_core_internet_gateway.{gw_ref}.id
            destination       = "0.0.0.0/0"
            destination_type  = "CIDR_BLOCK"
          }}
        }}
    """),

    # ── COMPUTE ───────────────────────────────────────────────────────────────
    "oci_core_instance": textwrap.dedent("""\
        data "oci_core_images" "ol8" {{
          compartment_id           = var.compartment_ocid
          operating_system         = "Oracle Linux"
          operating_system_version = "8"
          shape                    = "{shape}"
          sort_by                  = "TIMECREATED"
          sort_order               = "DESC"
        }}

        resource "oci_core_instance" "{name}" {{
          compartment_id      = var.compartment_ocid
          availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
          display_name        = "${{var.project_name}}-{name}"
          shape               = "{shape}"

          shape_config {{
            ocpus         = {ocpu}
            memory_in_gbs = {memory_gb}
          }}

          source_details {{
            source_type = "image"
            source_id   = data.oci_core_images.ol8.images[0].id
          }}

          create_vnic_details {{
            subnet_id        = oci_core_subnet.{subnet_ref}.id
            assign_public_ip = {assign_public_ip}
            nsg_ids          = [oci_core_network_security_group.{nsg_ref}.id]
          }}

          metadata = {{
            ssh_authorized_keys = var.ssh_public_key
          }}

          freeform_tags = {{
            "project"     = var.project_name
            "environment" = var.environment
            "role"        = "{role}"
          }}
        }}

        data "oci_identity_availability_domains" "ads" {{
          compartment_id = var.tenancy_ocid
        }}

        variable "ssh_public_key" {{
          description = "SSH public key for compute instances"
          type        = string
        }}
    """),

    "oci_core_instance_pool": textwrap.dedent("""\
        resource "oci_core_instance_configuration" "{name}_config" {{
          compartment_id = var.compartment_ocid
          display_name   = "${{var.project_name}}-{name}-config"

          instance_details {{
            instance_type = "compute"

            launch_details {{
              compartment_id = var.compartment_ocid
              shape          = "{shape}"

              shape_config {{
                ocpus         = {ocpu}
                memory_in_gbs = {memory_gb}
              }}

              source_details {{
                source_type = "image"
                image_id    = data.oci_core_images.ol8.images[0].id
              }}

              create_vnic_details {{
                subnet_id        = oci_core_subnet.{subnet_ref}.id
                assign_public_ip = false
                nsg_ids          = [oci_core_network_security_group.{nsg_ref}.id]
              }}
            }}
          }}
        }}

        resource "oci_core_instance_pool" "{name}" {{
          compartment_id            = var.compartment_ocid
          instance_configuration_id = oci_core_instance_configuration.{name}_config.id
          display_name              = "${{var.project_name}}-{name}-pool"
          size                      = {size}

          placement_configurations {{
            availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
            primary_subnet_id   = oci_core_subnet.{subnet_ref}.id
          }}

          placement_configurations {{
            availability_domain = data.oci_identity_availability_domains.ads.availability_domains[1].name
            primary_subnet_id   = oci_core_subnet.{subnet_ref}.id
          }}
        }}
    """),

    # ── LOAD BALANCER ─────────────────────────────────────────────────────────
    "oci_load_balancer_load_balancer": textwrap.dedent("""\
        resource "oci_load_balancer_load_balancer" "{name}" {{
          compartment_id = var.compartment_ocid
          display_name   = "${{var.project_name}}-lb"
          shape          = "flexible"
          is_private     = false
          subnet_ids     = [oci_core_subnet.{public_subnet_ref}.id]

          shape_details {{
            minimum_bandwidth_in_mbps = 10
            maximum_bandwidth_in_mbps = 400
          }}

          freeform_tags = {{
            "project"     = var.project_name
            "environment" = var.environment
          }}
        }}

        resource "oci_load_balancer_backend_set" "{name}_bs" {{
          load_balancer_id = oci_load_balancer_load_balancer.{name}.id
          name             = "backend-set"
          policy           = "ROUND_ROBIN"

          health_checker {{
            protocol            = "HTTP"
            port                = {backend_port}
            url_path            = "{health_check_path}"
            return_code         = 200
            timeout_in_millis   = 3000
            interval_in_millis  = 10000
          }}
        }}

        resource "oci_load_balancer_listener" "{name}_https" {{
          load_balancer_id         = oci_load_balancer_load_balancer.{name}.id
          name                     = "https-listener"
          port                     = 443
          protocol                 = "HTTP"
          default_backend_set_name = oci_load_balancer_backend_set.{name}_bs.name
        }}

        resource "oci_load_balancer_listener" "{name}_http" {{
          load_balancer_id         = oci_load_balancer_load_balancer.{name}.id
          name                     = "http-listener"
          port                     = 80
          protocol                 = "HTTP"
          default_backend_set_name = oci_load_balancer_backend_set.{name}_bs.name
        }}
    """),

    # ── STORAGE ───────────────────────────────────────────────────────────────
    "oci_objectstorage_bucket": textwrap.dedent("""\
        data "oci_objectstorage_namespace" "ns" {{
          compartment_id = var.compartment_ocid
        }}

        resource "oci_objectstorage_bucket" "{name}" {{
          compartment_id = var.compartment_ocid
          namespace      = data.oci_objectstorage_namespace.ns.namespace
          name           = "${{var.project_name}}-{bucket_name}"
          access_type    = "NoPublicAccess"
          storage_tier   = "{storage_tier}"
          versioning     = "Enabled"

          freeform_tags = {{
            "project"     = var.project_name
            "environment" = var.environment
          }}
        }}

        resource "oci_objectstorage_bucket_lifecycle_policy" "{name}_lifecycle" {{
          bucket    = oci_objectstorage_bucket.{name}.name
          namespace = data.oci_objectstorage_namespace.ns.namespace

          rules {{
            name           = "archive-old-objects"
            action         = "ARCHIVE"
            time_amount    = 90
            time_unit      = "DAYS"
            object_name_filter {{ }}
            is_enabled = true
          }}
        }}
    """),

    "oci_core_volume": textwrap.dedent("""\
        resource "oci_core_volume" "{name}" {{
          compartment_id      = var.compartment_ocid
          availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
          display_name        = "${{var.project_name}}-{name}"
          size_in_gbs         = {size_gb}
          vpus_per_gb         = {vpus_per_gb}

          freeform_tags = {{
            "project"     = var.project_name
            "environment" = var.environment
          }}
        }}

        resource "oci_core_volume_attachment" "{name}_attach" {{
          attachment_type = "paravirtualized"
          instance_id     = oci_core_instance.{instance_ref}.id
          volume_id       = oci_core_volume.{name}.id
          is_shareable    = false
        }}
    """),

    # ── DATABASE ──────────────────────────────────────────────────────────────
    "oci_database_autonomous_database": textwrap.dedent("""\
        resource "oci_database_autonomous_database" "{name}" {{
          compartment_id           = var.compartment_ocid
          display_name             = "${{var.project_name}}-{name}"
          db_name                  = "{db_name}"
          cpu_core_count           = {ocpu}
          data_storage_size_in_tbs = {storage_tb}
          db_workload              = "{workload}"  # OLTP or DW
          is_auto_scaling_enabled  = true
          is_free_tier             = false

          admin_password           = var.adb_admin_password

          # Network access
          whitelisted_ips          = []
          subnet_id                = oci_core_subnet.{subnet_ref}.id
          private_endpoint_label   = "{db_name}-pe"

          freeform_tags = {{
            "project"     = var.project_name
            "environment" = var.environment
          }}
        }}

        variable "adb_admin_password" {{
          description = "Autonomous Database admin password (12-30 chars, must contain upper, lower, digit, special)"
          type        = string
          sensitive   = true
        }}
    """),

    "oci_mysql_mysql_db_system": textwrap.dedent("""\
        resource "oci_mysql_mysql_db_system" "{name}" {{
          compartment_id      = var.compartment_ocid
          availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
          display_name        = "${{var.project_name}}-{name}"
          shape_name          = "MySQL.VM.Standard.E4.4.64GB"
          subnet_id           = oci_core_subnet.{subnet_ref}.id
          admin_username      = "mysqladmin"
          admin_password      = var.mysql_admin_password
          data_storage_size_in_gb = {storage_gb}
          port                = 3306
          port_x              = 33060
          is_highly_available = true

          backup_policy {{
            is_enabled        = true
            retention_in_days = 7
            window_start_time = "02:00"
          }}

          maintenance {{
            window_start_time = "sun 03:00"
          }}

          freeform_tags = {{
            "project"     = var.project_name
            "environment" = var.environment
          }}
        }}

        variable "mysql_admin_password" {{
          description = "MySQL administrator password"
          type        = string
          sensitive   = true
        }}
    """),

    # ── CONTAINER / OKE ───────────────────────────────────────────────────────
    "oci_containerengine_cluster": textwrap.dedent("""\
        resource "oci_containerengine_cluster" "{name}" {{
          compartment_id     = var.compartment_ocid
          vcn_id             = oci_core_vcn.{vcn_ref}.id
          name               = "${{var.project_name}}-oke"
          kubernetes_version = "{k8s_version}"
          type               = "ENHANCED_CLUSTER"

          endpoint_config {{
            is_public_ip_enabled = false
            subnet_id            = oci_core_subnet.{endpoint_subnet_ref}.id
            nsg_ids              = []
          }}

          options {{
            service_lb_subnet_ids = [oci_core_subnet.{lb_subnet_ref}.id]

            add_ons {{
              is_kubernetes_dashboard_enabled = false
              is_tiller_enabled               = false
            }}

            kubernetes_network_config {{
              pods_cidr     = "10.244.0.0/16"
              services_cidr = "10.96.0.0/16"
            }}

            persistent_volume_config {{
              freeform_tags = {{ "project" = var.project_name }}
            }}
          }}

          freeform_tags = {{
            "project"     = var.project_name
            "environment" = var.environment
          }}
        }}

        resource "oci_containerengine_node_pool" "{name}_nodes" {{
          cluster_id         = oci_containerengine_cluster.{name}.id
          compartment_id     = var.compartment_ocid
          name               = "${{var.project_name}}-nodepool"
          kubernetes_version = "{k8s_version}"
          node_shape         = "{node_shape}"

          node_shape_config {{
            ocpus         = {node_ocpu}
            memory_in_gbs = {node_memory_gb}
          }}

          node_source_details {{
            source_type = "IMAGE"
            image_id    = data.oci_core_images.ol8.images[0].id
          }}

          node_config_details {{
            size = {node_count}

            placement_configs {{
              availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
              subnet_id           = oci_core_subnet.{worker_subnet_ref}.id
            }}

            placement_configs {{
              availability_domain = data.oci_identity_availability_domains.ads.availability_domains[1].name
              subnet_id           = oci_core_subnet.{worker_subnet_ref}.id
            }}

            node_pool_pod_network_option_details {{
              cni_type          = "OCI_VCN_IP_NATIVE"
              pod_subnet_ids    = [oci_core_subnet.{worker_subnet_ref}.id]
              max_pods_per_node = 31
            }}
          }}

          initial_node_labels {{
            key   = "app"
            value = var.project_name
          }}
        }}
    """),

    # ── IDENTITY / SECURITY ────────────────────────────────────────────────────
    "oci_identity_compartment": textwrap.dedent("""\
        resource "oci_identity_compartment" "{name}" {{
          parent_id    = var.compartment_ocid
          name         = "${{var.project_name}}-{name}"
          description  = "{description}"
          enable_delete = false

          freeform_tags = {{
            "project" = var.project_name
          }}
        }}
    """),

    "oci_kms_vault": textwrap.dedent("""\
        resource "oci_kms_vault" "{name}" {{
          compartment_id = var.compartment_ocid
          display_name   = "${{var.project_name}}-vault"
          vault_type     = "DEFAULT"  # DEFAULT (virtual) or VIRTUAL_PRIVATE (HSM)

          freeform_tags = {{
            "project"     = var.project_name
            "environment" = var.environment
          }}
        }}

        resource "oci_kms_key" "{name}_master_key" {{
          compartment_id      = var.compartment_ocid
          display_name        = "${{var.project_name}}-master-key"
          management_endpoint = oci_kms_vault.{name}.management_endpoint

          key_shape {{
            algorithm = "AES"
            length    = 32  # 256-bit AES
          }}

          protection_mode = "SOFTWARE"
        }}
    """),

    # ── OUTPUTS ───────────────────────────────────────────────────────────────
    "outputs": textwrap.dedent("""\
        output "vcn_id" {{
          description = "VCN OCID"
          value       = oci_core_vcn.{vcn_ref}.id
        }}

        output "lb_public_ip" {{
          description = "Load Balancer public IP"
          value       = oci_load_balancer_load_balancer.{lb_ref}.ip_address_details[0].ip_address
        }}

        output "adb_connection_strings" {{
          description = "Autonomous Database connection strings"
          value       = oci_database_autonomous_database.{adb_ref}.connection_strings
          sensitive   = true
        }}

        output "oke_cluster_id" {{
          description = "OKE Cluster OCID"
          value       = oci_containerengine_cluster.{oke_ref}.id
        }}
    """),
}

# ---------------------------------------------------------------------------
# FULL MODULE TEMPLATES (multi-file bundles)
# ---------------------------------------------------------------------------

def _three_tier_module(project_name: str = "migration", region: str = "us-ashburn-1") -> Dict[str, str]:
    """Generate a complete 3-tier web application Terraform project."""
    return {
        "provider.tf": PROVIDER_TF,
        "variables.tf": VARIABLES_TF,
        "network.tf": textwrap.dedent(f"""\
            # ── VCN ────────────────────────────────────────────────────────────────
            resource "oci_core_vcn" "main" {{
              compartment_id = var.compartment_ocid
              display_name   = "${{var.project_name}}-vcn"
              cidr_blocks    = ["10.0.0.0/16"]
              dns_label      = replace(var.project_name, "-", "")
            }}

            resource "oci_core_internet_gateway" "igw" {{
              compartment_id = var.compartment_ocid
              vcn_id         = oci_core_vcn.main.id
              display_name   = "${{var.project_name}}-igw"
              enabled        = true
            }}

            resource "oci_core_nat_gateway" "natgw" {{
              compartment_id = var.compartment_ocid
              vcn_id         = oci_core_vcn.main.id
              display_name   = "${{var.project_name}}-natgw"
            }}

            resource "oci_core_service_gateway" "svcgw" {{
              compartment_id = var.compartment_ocid
              vcn_id         = oci_core_vcn.main.id
              display_name   = "${{var.project_name}}-svcgw"
              services {{
                service_id = data.oci_core_services.all.services[0].id
              }}
            }}

            data "oci_core_services" "all" {{
              filter {{
                name   = "name"
                values = ["All .* Services In Oracle Services Network"]
                regex  = true
              }}
            }}

            # ── ROUTE TABLES ────────────────────────────────────────────────────
            resource "oci_core_route_table" "public_rt" {{
              compartment_id = var.compartment_ocid
              vcn_id         = oci_core_vcn.main.id
              display_name   = "${{var.project_name}}-public-rt"

              route_rules {{
                network_entity_id = oci_core_internet_gateway.igw.id
                destination       = "0.0.0.0/0"
              }}
            }}

            resource "oci_core_route_table" "private_rt" {{
              compartment_id = var.compartment_ocid
              vcn_id         = oci_core_vcn.main.id
              display_name   = "${{var.project_name}}-private-rt"

              route_rules {{
                network_entity_id = oci_core_nat_gateway.natgw.id
                destination       = "0.0.0.0/0"
              }}

              route_rules {{
                network_entity_id = oci_core_service_gateway.svcgw.id
                destination       = "all-iad-services-in-oracle-services-network"
                destination_type  = "SERVICE_CIDR_BLOCK"
              }}
            }}

            # ── SUBNETS ─────────────────────────────────────────────────────────
            resource "oci_core_subnet" "public" {{
              compartment_id             = var.compartment_ocid
              vcn_id                     = oci_core_vcn.main.id
              display_name               = "${{var.project_name}}-public-subnet"
              cidr_block                 = "10.0.1.0/24"
              dns_label                  = "public"
              prohibit_public_ip_on_vnic = false
              route_table_id             = oci_core_route_table.public_rt.id
              security_list_ids          = [oci_core_security_list.lb_sl.id]
            }}

            resource "oci_core_subnet" "app" {{
              compartment_id             = var.compartment_ocid
              vcn_id                     = oci_core_vcn.main.id
              display_name               = "${{var.project_name}}-app-subnet"
              cidr_block                 = "10.0.2.0/24"
              dns_label                  = "app"
              prohibit_public_ip_on_vnic = true
              route_table_id             = oci_core_route_table.private_rt.id
              security_list_ids          = [oci_core_security_list.app_sl.id]
            }}

            resource "oci_core_subnet" "db" {{
              compartment_id             = var.compartment_ocid
              vcn_id                     = oci_core_vcn.main.id
              display_name               = "${{var.project_name}}-db-subnet"
              cidr_block                 = "10.0.3.0/24"
              dns_label                  = "db"
              prohibit_public_ip_on_vnic = true
              route_table_id             = oci_core_route_table.private_rt.id
              security_list_ids          = [oci_core_security_list.db_sl.id]
            }}
        """),
        "security.tf": textwrap.dedent("""\
            resource "oci_core_security_list" "lb_sl" {
              compartment_id = var.compartment_ocid
              vcn_id         = oci_core_vcn.main.id
              display_name   = "${var.project_name}-lb-sl"

              egress_security_rules {
                protocol    = "all"
                destination = "0.0.0.0/0"
              }
              ingress_security_rules {
                protocol = "6"
                source   = "0.0.0.0/0"
                tcp_options { min = 443; max = 443 }
              }
              ingress_security_rules {
                protocol = "6"
                source   = "0.0.0.0/0"
                tcp_options { min = 80; max = 80 }
              }
            }

            resource "oci_core_security_list" "app_sl" {
              compartment_id = var.compartment_ocid
              vcn_id         = oci_core_vcn.main.id
              display_name   = "${var.project_name}-app-sl"

              egress_security_rules {
                protocol    = "all"
                destination = "0.0.0.0/0"
              }
              ingress_security_rules {
                protocol = "6"
                source   = "10.0.1.0/24"
                tcp_options { min = 8080; max = 8080 }
              }
            }

            resource "oci_core_security_list" "db_sl" {
              compartment_id = var.compartment_ocid
              vcn_id         = oci_core_vcn.main.id
              display_name   = "${var.project_name}-db-sl"

              egress_security_rules {
                protocol    = "all"
                destination = "0.0.0.0/0"
              }
              ingress_security_rules {
                protocol = "6"
                source   = "10.0.2.0/24"
                tcp_options { min = 1521; max = 1521 }
              }
              ingress_security_rules {
                protocol = "6"
                source   = "10.0.2.0/24"
                tcp_options { min = 1522; max = 1522 }
              }
            }
        """),
        "compute.tf": textwrap.dedent("""\
            data "oci_identity_availability_domains" "ads" {
              compartment_id = var.tenancy_ocid
            }

            data "oci_core_images" "ol8" {
              compartment_id           = var.compartment_ocid
              operating_system         = "Oracle Linux"
              operating_system_version = "8"
              shape                    = var.app_shape
              sort_by                  = "TIMECREATED"
              sort_order               = "DESC"
            }

            variable "app_shape"        { default = "VM.Standard.E4.Flex" }
            variable "app_ocpu"         { default = 2 }
            variable "app_memory_gb"    { default = 16 }
            variable "app_instance_count" { default = 2 }
            variable "ssh_public_key"   { type = string }

            resource "oci_core_instance" "app" {
              count               = var.app_instance_count
              compartment_id      = var.compartment_ocid
              availability_domain = data.oci_identity_availability_domains.ads.availability_domains[count.index % 2].name
              display_name        = "${var.project_name}-app-${count.index + 1}"
              shape               = var.app_shape

              shape_config {
                ocpus         = var.app_ocpu
                memory_in_gbs = var.app_memory_gb
              }

              source_details {
                source_type = "image"
                source_id   = data.oci_core_images.ol8.images[0].id
              }

              create_vnic_details {
                subnet_id        = oci_core_subnet.app.id
                assign_public_ip = false
              }

              metadata = {
                ssh_authorized_keys = var.ssh_public_key
              }

              freeform_tags = {
                "project"     = var.project_name
                "environment" = var.environment
                "role"        = "app-server"
              }
            }
        """),
        "database.tf": textwrap.dedent("""\
            variable "adb_ocpu"       { default = 2 }
            variable "adb_storage_tb" { default = 1 }
            variable "adb_admin_password" {
              type      = string
              sensitive = true
            }

            resource "oci_database_autonomous_database" "atp" {
              compartment_id           = var.compartment_ocid
              display_name             = "${var.project_name}-atp"
              db_name                  = "${replace(var.project_name, "-", "")}db"
              cpu_core_count           = var.adb_ocpu
              data_storage_size_in_tbs = var.adb_storage_tb
              db_workload              = "OLTP"
              is_auto_scaling_enabled  = true
              admin_password           = var.adb_admin_password
              subnet_id                = oci_core_subnet.db.id
              private_endpoint_label   = "${replace(var.project_name, "-", "")}dbpe"
              whitelisted_ips          = []

              freeform_tags = {
                "project"     = var.project_name
                "environment" = var.environment
              }
            }
        """),
        "load_balancer.tf": textwrap.dedent("""\
            resource "oci_load_balancer_load_balancer" "main" {
              compartment_id = var.compartment_ocid
              display_name   = "${var.project_name}-lb"
              shape          = "flexible"
              is_private     = false
              subnet_ids     = [oci_core_subnet.public.id]

              shape_details {
                minimum_bandwidth_in_mbps = 10
                maximum_bandwidth_in_mbps = 400
              }

              freeform_tags = {
                "project"     = var.project_name
                "environment" = var.environment
              }
            }

            resource "oci_load_balancer_backend_set" "app_bs" {
              load_balancer_id = oci_load_balancer_load_balancer.main.id
              name             = "app-backend-set"
              policy           = "ROUND_ROBIN"

              health_checker {
                protocol           = "HTTP"
                port               = 8080
                url_path           = "/health"
                return_code        = 200
                timeout_in_millis  = 3000
                interval_in_millis = 10000
              }
            }

            resource "oci_load_balancer_backend" "app" {
              count            = var.app_instance_count
              load_balancer_id = oci_load_balancer_load_balancer.main.id
              backendset_name  = oci_load_balancer_backend_set.app_bs.name
              ip_address       = oci_core_instance.app[count.index].private_ip
              port             = 8080
            }

            resource "oci_load_balancer_listener" "https" {
              load_balancer_id         = oci_load_balancer_load_balancer.main.id
              name                     = "https"
              port                     = 443
              protocol                 = "HTTP"
              default_backend_set_name = oci_load_balancer_backend_set.app_bs.name
            }
        """),
        "outputs.tf": textwrap.dedent("""\
            output "load_balancer_public_ip" {
              description = "Public IP of the Load Balancer"
              value       = oci_load_balancer_load_balancer.main.ip_address_details[0].ip_address
            }

            output "atp_connection_strings" {
              description = "Autonomous Database connection strings"
              value       = oci_database_autonomous_database.atp.connection_strings
              sensitive   = true
            }

            output "vcn_id" {
              value = oci_core_vcn.main.id
            }

            output "app_instance_private_ips" {
              value = [for i in oci_core_instance.app : i.private_ip]
            }
        """),
    }


class TerraformGenServer:
    SERVER_NAME = "terraform_gen"
    VERSION = "2.0.0"

    def __init__(self):
        self._call_count = 0
        self._success_count = 0
        self._total_latency_ms = 0.0

    def _record(self, latency_ms: float, success: bool = True):
        self._call_count += 1
        if success:
            self._success_count += 1
        self._total_latency_ms += latency_ms

    # ------------------------------------------------------------------
    def generate_provider(self, region: str = "us-ashburn-1") -> Dict[str, Any]:
        """Return the provider.tf content."""
        t0 = time.time()
        self._record((time.time() - t0) * 1000)
        return {"file_name": "provider.tf", "content": PROVIDER_TF, "language": "hcl"}

    # ------------------------------------------------------------------
    def generate_variables(self, variables: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Return variables.tf with defaults plus user-supplied vars."""
        t0 = time.time()
        lines = [VARIABLES_TF]
        for v in (variables or []):
            desc = v.get("description", v["name"])
            typ  = v.get("type", "string")
            line = f'variable "{v["name"]}" {{\n  description = "{desc}"\n  type        = {typ}\n'
            if "default" in v:
                d = v["default"]
                line += f'  default     = "{d}"\n' if isinstance(d, str) else f'  default     = {d}\n'
            line += "}\n"
            lines.append(line)
        content = "\n".join(lines)
        self._record((time.time() - t0) * 1000)
        return {"file_name": "variables.tf", "content": content, "variable_count": len(variables or [])}

    # ------------------------------------------------------------------
    def generate_resource(
        self,
        resource_type: str,
        resource_name: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a Terraform resource block from a template."""
        t0 = time.time()
        template = _RESOURCE_TEMPLATES.get(resource_type)
        if template:
            # Merge resource_name into config and format
            ctx = {**config, "name": resource_name}
            # Fill in defaults for unset keys
            defaults = {
                "cidr_block": "10.0.0.0/16", "vcn_ref": "main",
                "subnet_ref": "app", "nsg_ref": "app_nsg",
                "shape": "VM.Standard.E4.Flex", "ocpu": 2, "memory_gb": 16,
                "assign_public_ip": "false", "role": "app",
                "prohibit_public_ip": "true", "subnet_type": "app",
                "dns_label": resource_name.replace("-", ""),
                "security_list_ref": "app_sl", "route_table_ref": "app_rt",
                "ingress_cidr": "10.0.0.0/8", "port_min": 8080, "port_max": 8080,
                "tier": "app", "gw_ref": "igw",
                "bucket_name": resource_name, "storage_tier": "Standard",
                "size_gb": 100, "vpus_per_gb": 10, "instance_ref": "app",
                "db_name": resource_name.replace("-", "")[:12],
                "storage_tb": 1, "workload": "OLTP",
                "public_subnet_ref": "public", "backend_port": 8080,
                "health_check_path": "/health",
                "k8s_version": "v1.29.1", "node_shape": "VM.Standard.E4.Flex",
                "node_ocpu": 2, "node_memory_gb": 16, "node_count": 3,
                "endpoint_subnet_ref": "app", "lb_subnet_ref": "public",
                "worker_subnet_ref": "app", "description": resource_name,
                "storage_gb": 100,
            }
            for k, v in defaults.items():
                ctx.setdefault(k, v)
            try:
                content = template.format(**ctx)
            except KeyError as e:
                content = template  # Return raw template if format fails
        else:
            # Generic fallback
            display = config.get("name", resource_name)
            content = (
                f'resource "{resource_type}" "{resource_name}" {{\n'
                f'  compartment_id = var.compartment_ocid\n'
                f'  display_name   = "{display}"\n'
                "}\n"
            )

        self._record((time.time() - t0) * 1000)
        return {
            "resource_type": resource_type,
            "resource_name": resource_name,
            "content": content,
            "template_found": template is not None,
        }

    # ------------------------------------------------------------------
    def generate_module(
        self,
        module_name: str,
        source: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a Terraform module {} block."""
        t0 = time.time()
        parts = [f'module "{module_name}" {{\n  source = "{source}"\n']
        for k, v in variables.items():
            if isinstance(v, str) and not v.startswith("var.") and not v.startswith("oci_"):
                parts.append(f'  {k} = "{v}"\n')
            else:
                parts.append(f'  {k} = {v}\n')
        parts.append("}\n")
        self._record((time.time() - t0) * 1000)
        return {"module_name": module_name, "content": "".join(parts)}

    # ------------------------------------------------------------------
    def generate_three_tier_project(
        self,
        project_name: str = "migration",
        region: str = "us-ashburn-1",
    ) -> Dict[str, Any]:
        """Generate a complete 3-tier OCI Terraform project (multi-file)."""
        t0 = time.time()
        files = _three_tier_module(project_name, region)
        self._record((time.time() - t0) * 1000)
        return {
            "project_name": project_name,
            "files": files,
            "file_count": len(files),
            "description": "3-tier web application: LB → App VMs → Autonomous DB",
        }

    # ------------------------------------------------------------------
    def list_resource_types(self) -> Dict[str, Any]:
        """List all supported OCI resource types."""
        return {
            "resource_types": list(_RESOURCE_TEMPLATES.keys()),
            "count": len(_RESOURCE_TEMPLATES),
        }

    # ------------------------------------------------------------------
    def get_health_metrics(self) -> Dict[str, Any]:
        avg = self._total_latency_ms / max(self._call_count, 1)
        return {
            "server":              self.SERVER_NAME,
            "version":             self.VERSION,
            "total_calls":         self._call_count,
            "success_rate":        round(self._success_count / max(self._call_count, 1), 4),
            "avg_latency_ms":      round(avg, 2),
            "status":              "healthy",
            "supported_resources": len(_RESOURCE_TEMPLATES),
        }


terraform_gen_server = TerraformGenServer()
