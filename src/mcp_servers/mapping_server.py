"""MCP Server 4: Multi-Cloud → OCI Service Mapping.

Comprehensive mapping of AWS, Azure, and GCP services to OCI equivalents.
Includes confidence scores, Terraform resource types, migration notes,
and category-based grouping.

References:
  https://docs.oracle.com/en-us/iaas/Content/services.htm
  https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/terraform.htm
"""
import time
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# SERVICE MAPPING SCHEMA:
#   oci_service       – human-readable OCI service name
#   oci_resource      – Terraform resource type
#   oci_doc_url       – OCI documentation URL
#   category          – logical grouping
#   confidence        – 0.0-1.0 feature-parity confidence
#   migration_effort  – low / medium / high
#   notes             – migration guidance
# ---------------------------------------------------------------------------

AWS_TO_OCI: Dict[str, Dict] = {
    # ── COMPUTE ──────────────────────────────────────────────────────────────
    "EC2": {
        "oci_service": "Compute",
        "oci_resource": "oci_core_instance",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/Compute/home.htm",
        "category": "Compute",
        "confidence": 0.96,
        "migration_effort": "low",
        "notes": "Use VM.Standard.E4.Flex for x86 or A1.Flex for ARM. AMI → Custom Image.",
    },
    "LAMBDA": {
        "oci_service": "OCI Functions",
        "oci_resource": "oci_functions_function",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/Functions/home.htm",
        "category": "Serverless",
        "confidence": 0.92,
        "migration_effort": "medium",
        "notes": "Fn Project-based. Container images supported. Cold-start behaviour similar.",
    },
    "EKS": {
        "oci_service": "Oracle Container Engine for Kubernetes (OKE)",
        "oci_resource": "oci_containerengine_cluster",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm",
        "category": "Kubernetes",
        "confidence": 0.95,
        "migration_effort": "medium",
        "notes": "OKE control plane is free. CNCF-conformant Kubernetes. Migrate manifests directly.",
    },
    "ECS": {
        "oci_service": "OCI Container Instances",
        "oci_resource": "oci_container_instances_container_instance",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/container-instances/home.htm",
        "category": "Containers",
        "confidence": 0.88,
        "migration_effort": "medium",
        "notes": "Serverless containers. For orchestration-heavy workloads prefer OKE.",
    },
    "FARGATE": {
        "oci_service": "OCI Container Instances",
        "oci_resource": "oci_container_instances_container_instance",
        "category": "Containers",
        "confidence": 0.87,
        "migration_effort": "medium",
        "notes": "Serverless compute for containers. OCI Container Instances is the closest match.",
    },
    "LIGHTSAIL": {
        "oci_service": "Compute (with simplified shape)",
        "oci_resource": "oci_core_instance",
        "category": "Compute",
        "confidence": 0.85,
        "migration_effort": "low",
        "notes": "Use small E4.Flex or A1.Flex shapes for similar simple VPS workloads.",
    },
    # ── STORAGE ──────────────────────────────────────────────────────────────
    "S3": {
        "oci_service": "Object Storage",
        "oci_resource": "oci_objectstorage_bucket",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/Object/home.htm",
        "category": "Object Storage",
        "confidence": 0.98,
        "migration_effort": "low",
        "notes": "S3-compatible API (pre-authenticated requests, lifecycle policies). aws s3 sync → oci os object bulk-upload.",
    },
    "S3 GLACIER": {
        "oci_service": "Archive Storage",
        "oci_resource": "oci_objectstorage_bucket",
        "category": "Archive",
        "confidence": 0.93,
        "migration_effort": "low",
        "notes": "Set storage tier to 'Archive'. Restore times: 1 hr (Standard) vs. 4-24 hrs.",
    },
    "EBS": {
        "oci_service": "Block Volume",
        "oci_resource": "oci_core_volume",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/Block/home.htm",
        "category": "Block Storage",
        "confidence": 0.95,
        "migration_effort": "low",
        "notes": "VPU controls IOPS. Default 10 VPU = ~2000 IOPS/TB. Max 120 VPU (Ultra High).",
    },
    "EFS": {
        "oci_service": "File Storage",
        "oci_resource": "oci_file_storage_file_system",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/File/home.htm",
        "category": "File Storage",
        "confidence": 0.93,
        "migration_effort": "low",
        "notes": "NFS v3 compatible. Mount targets per AD. Supports snapshots.",
    },
    "STORAGE GATEWAY": {
        "oci_service": "Storage Gateway",
        "oci_resource": "oci_storage_gateway_gateway",
        "category": "Hybrid Storage",
        "confidence": 0.80,
        "migration_effort": "medium",
        "notes": "OCI Storage Gateway is a VM appliance for on-premises to OCI Object Storage.",
    },
    # ── DATABASE ─────────────────────────────────────────────────────────────
    "RDS": {
        "oci_service": "MySQL HeatWave / Autonomous Database / Base Database",
        "oci_resource": "oci_mysql_mysql_db_system",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/mysql-database/doc/overview-mysql-database-service.html",
        "category": "Database",
        "confidence": 0.90,
        "migration_effort": "medium",
        "notes": "MySQL→MySQL HeatWave; PostgreSQL/Oracle→Autonomous DB EE; SQL Server→Oracle EE or Autonomous.",
    },
    "RDS AURORA": {
        "oci_service": "MySQL HeatWave",
        "oci_resource": "oci_mysql_mysql_db_system",
        "category": "Database",
        "confidence": 0.87,
        "migration_effort": "medium",
        "notes": "Aurora MySQL → MySQL HeatWave (HA, read replicas). Aurora PostgreSQL → Autonomous DB.",
    },
    "DYNAMODB": {
        "oci_service": "NoSQL Database Cloud Service",
        "oci_resource": "oci_nosql_table",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/nosql-database/doc/overview.html",
        "category": "NoSQL",
        "confidence": 0.90,
        "migration_effort": "medium",
        "notes": "OCI NoSQL: serverless, JSON documents, secondary indexes, TTL. DynamoDB Streams → OCI Streaming.",
    },
    "ELASTICACHE REDIS": {
        "oci_service": "OCI Cache (Redis-compatible)",
        "oci_resource": "oci_redis_redis_cluster",
        "category": "Cache",
        "confidence": 0.92,
        "migration_effort": "low",
        "notes": "Redis 7 compatible, managed, HA with replication.",
    },
    "ELASTICACHE MEMCACHED": {
        "oci_service": "OCI Cache (Redis-compatible)",
        "oci_resource": "oci_redis_redis_cluster",
        "category": "Cache",
        "confidence": 0.78,
        "migration_effort": "medium",
        "notes": "OCI Cache is Redis-based; refactor Memcached clients to use Redis protocol.",
    },
    "REDSHIFT": {
        "oci_service": "Autonomous Data Warehouse (ADW)",
        "oci_resource": "oci_database_autonomous_database",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/autonomous-database/doc/autonomous-data-warehouse.html",
        "category": "Data Warehouse",
        "confidence": 0.88,
        "migration_effort": "high",
        "notes": "ADW: Oracle SQL, JSON, ML. Use OCI Migration Service or Data Integration for ETL.",
    },
    # ── NETWORKING ────────────────────────────────────────────────────────────
    "VPC": {
        "oci_service": "Virtual Cloud Network (VCN)",
        "oci_resource": "oci_core_vcn",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/managingVCNs_topic-Overview_of_VCNs_and_Subnets.htm",
        "category": "Networking",
        "confidence": 0.99,
        "migration_effort": "low",
        "notes": "VCN = VPC. Map subnets → OCI subnets (public/private). Security groups → Security Lists / NSGs.",
    },
    "SUBNET": {
        "oci_service": "VCN Subnet",
        "oci_resource": "oci_core_subnet",
        "category": "Networking",
        "confidence": 0.98,
        "migration_effort": "low",
        "notes": "OCI subnets are AD-scoped (regional in some cases). Public/private determined by route table.",
    },
    "SECURITY GROUP": {
        "oci_service": "Network Security Group (NSG) / Security List",
        "oci_resource": "oci_core_network_security_group",
        "category": "Networking",
        "confidence": 0.95,
        "migration_effort": "low",
        "notes": "NSGs attach to VNICs (more granular). Security Lists are subnet-level. Both support stateful rules.",
    },
    "ELB": {
        "oci_service": "Load Balancer (Flexible)",
        "oci_resource": "oci_load_balancer_load_balancer",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/Balance/home.htm",
        "category": "Load Balancing",
        "confidence": 0.95,
        "migration_effort": "low",
        "notes": "Flexible L7 LB with SSL termination, cookie-based stickiness, health checks.",
    },
    "NLB": {
        "oci_service": "Network Load Balancer",
        "oci_resource": "oci_network_load_balancer_network_load_balancer",
        "category": "Load Balancing",
        "confidence": 0.93,
        "migration_effort": "low",
        "notes": "Ultra-low latency L4 LB. NLB control plane is free.",
    },
    "API GATEWAY": {
        "oci_service": "OCI API Gateway",
        "oci_resource": "oci_apigateway_gateway",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/APIGateway/home.htm",
        "category": "API Management",
        "confidence": 0.90,
        "migration_effort": "medium",
        "notes": "Supports REST, HTTP, and WebSocket backends. OpenAPI import supported.",
    },
    "ROUTE53": {
        "oci_service": "DNS (OCI Public/Private DNS)",
        "oci_resource": "oci_dns_zone",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/DNS/home.htm",
        "category": "DNS",
        "confidence": 0.92,
        "migration_effort": "low",
        "notes": "Health checks, traffic steering, DNSSEC supported. Migrate zone files with standard BIND.",
    },
    "CLOUDFRONT": {
        "oci_service": "OCI Web Application Acceleration / CDN (via Akamai)",
        "oci_resource": "oci_waas_waas_policy",
        "category": "CDN",
        "confidence": 0.78,
        "migration_effort": "medium",
        "notes": "OCI partners with Akamai for CDN. OCI WAF includes basic caching.",
    },
    "TRANSIT GATEWAY": {
        "oci_service": "Dynamic Routing Gateway (DRG) v2",
        "oci_resource": "oci_core_drg",
        "category": "Networking",
        "confidence": 0.92,
        "migration_effort": "low",
        "notes": "DRG v2 supports VCN attachments, IPSec, FastConnect, and remote peering.",
    },
    "VPN GATEWAY": {
        "oci_service": "VPN Connect (IPSec)",
        "oci_resource": "oci_core_ip_sec_connection",
        "category": "Networking",
        "confidence": 0.93,
        "migration_effort": "low",
        "notes": "IKEv1/IKEv2, BGP routing, multiple tunnels for HA.",
    },
    "DIRECT CONNECT": {
        "oci_service": "FastConnect",
        "oci_resource": "oci_core_virtual_circuit",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/fastconnect.htm",
        "category": "Connectivity",
        "confidence": 0.95,
        "migration_effort": "medium",
        "notes": "1 Gbps, 10 Gbps circuits. Co-lo in Equinix/Megaport. SLA-backed.",
    },
    # ── IDENTITY & SECURITY ───────────────────────────────────────────────────
    "IAM": {
        "oci_service": "Identity and Access Management (IAM)",
        "oci_resource": "oci_identity_policy",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm",
        "category": "Identity",
        "confidence": 0.95,
        "migration_effort": "medium",
        "notes": "OCI uses compartments + policies. Roles → Groups+Policies. Trust policy → Dynamic Groups.",
    },
    "KMS": {
        "oci_service": "Vault (Key Management)",
        "oci_resource": "oci_kms_vault",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/KeyManagement/home.htm",
        "category": "Security",
        "confidence": 0.93,
        "migration_effort": "low",
        "notes": "Virtual or HSM-backed vaults. AES-256, RSA-2048/4096. FIPS 140-2 Level 3 for HSM.",
    },
    "SECRETS MANAGER": {
        "oci_service": "Vault Secrets",
        "oci_resource": "oci_vault_secret",
        "category": "Security",
        "confidence": 0.91,
        "migration_effort": "low",
        "notes": "Store, rotate, retrieve secrets. Integrates with OCI SDK and Functions.",
    },
    "WAF": {
        "oci_service": "Web Application Firewall (WAF)",
        "oci_resource": "oci_waf_web_app_firewall",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/WAF/home.htm",
        "category": "Security",
        "confidence": 0.90,
        "migration_effort": "low",
        "notes": "OWASP Top 10 protection, bot management, rate limiting.",
    },
    "SHIELD": {
        "oci_service": "DDoS Protection (built-in)",
        "oci_resource": "N/A (platform-level)",
        "category": "Security",
        "confidence": 0.85,
        "migration_effort": "low",
        "notes": "OCI includes volumetric DDoS protection by default at no extra cost.",
    },
    "GUARDDUTY": {
        "oci_service": "Cloud Guard",
        "oci_resource": "oci_cloud_guard_target",
        "category": "Security",
        "confidence": 0.85,
        "migration_effort": "low",
        "notes": "Cloud Guard detects misconfigurations and threats. Free for basic usage.",
    },
    "COGNITO": {
        "oci_service": "Oracle Identity Cloud Service (IDCS) / OCI IAM Domains",
        "oci_resource": "oci_identity_domain",
        "category": "Identity",
        "confidence": 0.82,
        "migration_effort": "high",
        "notes": "IDCS supports OIDC, SAML, MFA. SCIM provisioning. JWT token integration.",
    },
    # ── MESSAGING / EVENTING ─────────────────────────────────────────────────
    "SNS": {
        "oci_service": "Notifications (ONS)",
        "oci_resource": "oci_ons_notification_topic",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/Notification/home.htm",
        "category": "Messaging",
        "confidence": 0.88,
        "migration_effort": "low",
        "notes": "HTTP/S, email, PagerDuty, Slack subscriptions. Fan-out pattern supported.",
    },
    "SQS": {
        "oci_service": "OCI Queue",
        "oci_resource": "oci_queue_queue",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/queue/home.htm",
        "category": "Messaging",
        "confidence": 0.88,
        "migration_effort": "low",
        "notes": "At-least-once delivery, visibility timeout, dead-letter queue support.",
    },
    "KINESIS": {
        "oci_service": "OCI Streaming",
        "oci_resource": "oci_streaming_stream",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/Streaming/home.htm",
        "category": "Streaming",
        "confidence": 0.87,
        "migration_effort": "medium",
        "notes": "Kafka-compatible API. Partitions, consumer groups, retention up to 7 days.",
    },
    "EVENTBRIDGE": {
        "oci_service": "OCI Events",
        "oci_resource": "oci_events_rule",
        "category": "Eventing",
        "confidence": 0.85,
        "migration_effort": "medium",
        "notes": "Event rules trigger Functions, Notifications, Streaming on OCI resource state changes.",
    },
    "MQ": {
        "oci_service": "OCI Queue",
        "oci_resource": "oci_queue_queue",
        "category": "Messaging",
        "confidence": 0.75,
        "migration_effort": "high",
        "notes": "OCI Queue is SQS-like. For AMQP/JMS heavy usage, consider self-managed RabbitMQ on OCI Compute.",
    },
    # ── MONITORING / OBSERVABILITY ────────────────────────────────────────────
    "CLOUDWATCH": {
        "oci_service": "Monitoring + Logging",
        "oci_resource": "oci_monitoring_alarm",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/Monitoring/home.htm",
        "category": "Monitoring",
        "confidence": 0.88,
        "migration_effort": "medium",
        "notes": "OCI Monitoring for metrics/alarms. OCI Logging for log aggregation. Logging Analytics for search.",
    },
    "CLOUDTRAIL": {
        "oci_service": "Audit Service",
        "oci_resource": "oci_audit_configuration",
        "category": "Audit",
        "confidence": 0.92,
        "migration_effort": "low",
        "notes": "All OCI API calls are audited by default. Audit events stream to OCI Logging/Object Storage.",
    },
    "X-RAY": {
        "oci_service": "OCI APM (Application Performance Monitoring)",
        "oci_resource": "oci_apm_apm_domain",
        "category": "Observability",
        "confidence": 0.82,
        "migration_effort": "medium",
        "notes": "OpenTelemetry-compatible tracing, synthetic monitoring, browser RUM.",
    },
    # ── ANALYTICS / DATA ─────────────────────────────────────────────────────
    "GLUE": {
        "oci_service": "OCI Data Integration",
        "oci_resource": "oci_data_integration_workspace",
        "category": "Data Integration",
        "confidence": 0.82,
        "migration_effort": "high",
        "notes": "Visual ETL designer, Spark-based. Can connect to ADW, Object Storage, HeatWave.",
    },
    "ATHENA": {
        "oci_service": "Autonomous Data Warehouse (ADW) with Object Storage",
        "oci_resource": "oci_database_autonomous_database",
        "category": "Analytics",
        "confidence": 0.80,
        "migration_effort": "medium",
        "notes": "Use External Tables or DBMS_CLOUD in ADW to query Parquet/ORC in Object Storage.",
    },
    "EMR": {
        "oci_service": "OCI Big Data Service (BDS)",
        "oci_resource": "oci_bds_bds_instance",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/bigdata/home.htm",
        "category": "Big Data",
        "confidence": 0.83,
        "migration_effort": "high",
        "notes": "Managed Hadoop/Spark. Auto-scaling worker nodes. Integrates with OCI Object Storage (HDFS-compatible).",
    },
    "QUICKSIGHT": {
        "oci_service": "Oracle Analytics Cloud (OAC)",
        "oci_resource": "oci_analytics_analytics_instance",
        "category": "Analytics",
        "confidence": 0.80,
        "migration_effort": "medium",
        "notes": "OAC has ML augmentation, self-service BI, narrative AI. Supports ADW, MySQL HW, Object Storage.",
    },
    # ── DEVELOPER TOOLS / CI-CD ───────────────────────────────────────────────
    "CODECOMMIT": {
        "oci_service": "OCI DevOps (Code Repository)",
        "oci_resource": "oci_devops_repository",
        "category": "DevOps",
        "confidence": 0.85,
        "migration_effort": "low",
        "notes": "Git-compatible code repos. Free. Also compatible with GitHub/GitLab mirroring.",
    },
    "CODEBUILD": {
        "oci_service": "OCI DevOps (Build Pipeline)",
        "oci_resource": "oci_devops_build_pipeline",
        "category": "DevOps",
        "confidence": 0.83,
        "migration_effort": "medium",
        "notes": "Managed build service. Custom build runners, multi-stage pipelines.",
    },
    "CODEDEPLOY": {
        "oci_service": "OCI DevOps (Deployment Pipeline)",
        "oci_resource": "oci_devops_deploy_pipeline",
        "category": "DevOps",
        "confidence": 0.83,
        "migration_effort": "medium",
        "notes": "Blue/green, canary deployments to Compute, OKE, Functions.",
    },
    "CODEPIPELINE": {
        "oci_service": "OCI DevOps (Full Pipeline)",
        "oci_resource": "oci_devops_build_pipeline",
        "category": "DevOps",
        "confidence": 0.82,
        "migration_effort": "medium",
        "notes": "Integrates Code Repository + Build + Deploy pipelines end-to-end.",
    },
    "ECR": {
        "oci_service": "Container Registry (OCIR)",
        "oci_resource": "oci_artifacts_container_repository",
        "category": "Containers",
        "confidence": 0.95,
        "migration_effort": "low",
        "notes": "Docker-compatible registry. Push/pull with token auth. Free (storage billed at OS rates).",
    },
    # ── MANAGEMENT ────────────────────────────────────────────────────────────
    "CLOUDFORMATION": {
        "oci_service": "OCI Resource Manager (Terraform)",
        "oci_resource": "oci_resourcemanager_stack",
        "oci_doc_url": "https://docs.oracle.com/en-us/iaas/Content/ResourceManager/home.htm",
        "category": "IaC",
        "confidence": 0.88,
        "migration_effort": "high",
        "notes": "Convert CFN templates → Terraform using cf2tf or manual rewrite. ORM hosts Terraform state.",
    },
    "SYSTEMS MANAGER": {
        "oci_service": "OS Management Hub / Bastion Service",
        "oci_resource": "oci_os_management_hub_managed_instance",
        "category": "Management",
        "confidence": 0.78,
        "migration_effort": "medium",
        "notes": "OS Management Hub for patching/compliance. Bastion for SSH access without public IPs.",
    },
    "CONFIG": {
        "oci_service": "Cloud Guard + Security Zones",
        "oci_resource": "oci_cloud_guard_target",
        "category": "Governance",
        "confidence": 0.80,
        "migration_effort": "low",
        "notes": "Cloud Guard continuously assesses resource configuration against security recipes.",
    },
    "ORGANIZATIONS": {
        "oci_service": "OCI Organizations (Tenancy Management)",
        "oci_resource": "oci_tenantmanagercontrolplane_organization",
        "category": "Governance",
        "confidence": 0.80,
        "migration_effort": "medium",
        "notes": "Multi-tenancy governance. Landing Zone automates compartment and policy hierarchy.",
    },
    "COST EXPLORER": {
        "oci_service": "OCI Cost & Usage Reports",
        "oci_resource": "N/A (console/API)",
        "category": "FinOps",
        "confidence": 0.85,
        "migration_effort": "low",
        "notes": "Cost Analysis, Usage Reports, Budgets & Alerts in OCI Console.",
    },
}

# ---------------------------------------------------------------------------
# AZURE → OCI MAPPINGS
# ---------------------------------------------------------------------------
AZURE_TO_OCI: Dict[str, Dict] = {
    "VIRTUAL MACHINE":         {"oci_service": "Compute",                         "oci_resource": "oci_core_instance",                    "category": "Compute",        "confidence": 0.95, "migration_effort": "low"},
    "AKS":                     {"oci_service": "OKE",                              "oci_resource": "oci_containerengine_cluster",          "category": "Kubernetes",     "confidence": 0.95, "migration_effort": "medium"},
    "AZURE FUNCTIONS":         {"oci_service": "OCI Functions",                    "oci_resource": "oci_functions_function",               "category": "Serverless",     "confidence": 0.90, "migration_effort": "medium"},
    "BLOB STORAGE":            {"oci_service": "Object Storage",                   "oci_resource": "oci_objectstorage_bucket",             "category": "Object Storage", "confidence": 0.97, "migration_effort": "low"},
    "AZURE FILES":             {"oci_service": "File Storage",                     "oci_resource": "oci_file_storage_file_system",         "category": "File Storage",   "confidence": 0.92, "migration_effort": "low"},
    "MANAGED DISKS":           {"oci_service": "Block Volume",                     "oci_resource": "oci_core_volume",                      "category": "Block Storage",  "confidence": 0.95, "migration_effort": "low"},
    "AZURE SQL":               {"oci_service": "Autonomous Database OLTP",         "oci_resource": "oci_database_autonomous_database",     "category": "Database",       "confidence": 0.85, "migration_effort": "high"},
    "AZURE DATABASE MYSQL":    {"oci_service": "MySQL HeatWave",                   "oci_resource": "oci_mysql_mysql_db_system",            "category": "Database",       "confidence": 0.95, "migration_effort": "low"},
    "AZURE DATABASE POSTGRES": {"oci_service": "Autonomous Database (PostgreSQL mode)", "oci_resource": "oci_database_autonomous_database","category": "Database",       "confidence": 0.83, "migration_effort": "medium"},
    "COSMOS DB":               {"oci_service": "NoSQL Database",                   "oci_resource": "oci_nosql_table",                     "category": "NoSQL",          "confidence": 0.82, "migration_effort": "medium", "notes": "API-compatibility varies; NoSQL uses Tables/JSON model."},
    "AZURE CACHE REDIS":       {"oci_service": "OCI Cache (Redis)",                "oci_resource": "oci_redis_redis_cluster",              "category": "Cache",          "confidence": 0.93, "migration_effort": "low"},
    "VIRTUAL NETWORK":         {"oci_service": "Virtual Cloud Network (VCN)",      "oci_resource": "oci_core_vcn",                         "category": "Networking",     "confidence": 0.98, "migration_effort": "low"},
    "VNET GATEWAY":            {"oci_service": "DRG + VPN Connect",                "oci_resource": "oci_core_drg",                         "category": "Networking",     "confidence": 0.88, "migration_effort": "medium"},
    "EXPRESSROUTE":            {"oci_service": "FastConnect",                      "oci_resource": "oci_core_virtual_circuit",             "category": "Connectivity",   "confidence": 0.95, "migration_effort": "medium"},
    "AZURE LOAD BALANCER":     {"oci_service": "Network Load Balancer",            "oci_resource": "oci_network_load_balancer_network_load_balancer","category": "Load Balancing","confidence": 0.90,"migration_effort": "low"},
    "APPLICATION GATEWAY":     {"oci_service": "Load Balancer (Flexible)",         "oci_resource": "oci_load_balancer_load_balancer",      "category": "Load Balancing", "confidence": 0.88, "migration_effort": "low"},
    "AZURE FRONT DOOR":        {"oci_service": "WAF + CDN (Akamai)",               "oci_resource": "oci_waf_web_app_firewall",             "category": "CDN/Security",   "confidence": 0.75, "migration_effort": "high"},
    "AZURE ACTIVE DIRECTORY":  {"oci_service": "OCI IAM Domains (IDCS)",           "oci_resource": "oci_identity_domain",                  "category": "Identity",       "confidence": 0.82, "migration_effort": "high"},
    "KEY VAULT":               {"oci_service": "Vault (Key Management)",           "oci_resource": "oci_kms_vault",                        "category": "Security",       "confidence": 0.93, "migration_effort": "low"},
    "AZURE MONITOR":           {"oci_service": "Monitoring + Logging",             "oci_resource": "oci_monitoring_alarm",                 "category": "Monitoring",     "confidence": 0.85, "migration_effort": "medium"},
    "AZURE DEVOPS":            {"oci_service": "OCI DevOps",                       "oci_resource": "oci_devops_build_pipeline",            "category": "DevOps",         "confidence": 0.80, "migration_effort": "high"},
    "AZURE CONTAINER REGISTRY":{"oci_service": "Container Registry (OCIR)",        "oci_resource": "oci_artifacts_container_repository",   "category": "Containers",     "confidence": 0.95, "migration_effort": "low"},
    "SERVICE BUS":             {"oci_service": "OCI Queue / Streaming",            "oci_resource": "oci_queue_queue",                      "category": "Messaging",      "confidence": 0.83, "migration_effort": "medium"},
    "EVENT HUB":               {"oci_service": "OCI Streaming (Kafka-compatible)", "oci_resource": "oci_streaming_stream",                 "category": "Streaming",      "confidence": 0.88, "migration_effort": "medium"},
    "EVENT GRID":              {"oci_service": "OCI Events",                       "oci_resource": "oci_events_rule",                      "category": "Eventing",       "confidence": 0.82, "migration_effort": "medium"},
    "AZURE DATA FACTORY":      {"oci_service": "OCI Data Integration",             "oci_resource": "oci_data_integration_workspace",       "category": "Data Integration","confidence": 0.82, "migration_effort": "high"},
    "AZURE SYNAPSE":           {"oci_service": "Autonomous Data Warehouse (ADW)",  "oci_resource": "oci_database_autonomous_database",     "category": "Analytics",      "confidence": 0.80, "migration_effort": "high"},
    "POWER BI":                {"oci_service": "Oracle Analytics Cloud (OAC)",     "oci_resource": "oci_analytics_analytics_instance",     "category": "Analytics",      "confidence": 0.78, "migration_effort": "medium"},
    "AZURE RESOURCE MANAGER":  {"oci_service": "OCI Resource Manager (Terraform)", "oci_resource": "oci_resourcemanager_stack",            "category": "IaC",            "confidence": 0.85, "migration_effort": "high"},
}

# ---------------------------------------------------------------------------
# GCP → OCI MAPPINGS
# ---------------------------------------------------------------------------
GCP_TO_OCI: Dict[str, Dict] = {
    "COMPUTE ENGINE":          {"oci_service": "Compute",                         "oci_resource": "oci_core_instance",                    "category": "Compute",        "confidence": 0.95, "migration_effort": "low"},
    "GKE":                     {"oci_service": "OKE",                              "oci_resource": "oci_containerengine_cluster",          "category": "Kubernetes",     "confidence": 0.95, "migration_effort": "medium"},
    "CLOUD FUNCTIONS":         {"oci_service": "OCI Functions",                    "oci_resource": "oci_functions_function",               "category": "Serverless",     "confidence": 0.88, "migration_effort": "medium"},
    "CLOUD RUN":               {"oci_service": "OCI Container Instances",          "oci_resource": "oci_container_instances_container_instance","category": "Containers","confidence": 0.85, "migration_effort": "medium"},
    "CLOUD STORAGE":           {"oci_service": "Object Storage",                   "oci_resource": "oci_objectstorage_bucket",             "category": "Object Storage", "confidence": 0.97, "migration_effort": "low"},
    "CLOUD SQL":               {"oci_service": "MySQL HeatWave / Autonomous DB",   "oci_resource": "oci_mysql_mysql_db_system",            "category": "Database",       "confidence": 0.88, "migration_effort": "medium"},
    "CLOUD SPANNER":           {"oci_service": "Autonomous Database (Global)",     "oci_resource": "oci_database_autonomous_database",     "category": "Database",       "confidence": 0.72, "migration_effort": "high", "notes": "Spanner's global distributed model differs; evaluate OCI Global Distributed DB."},
    "FIRESTORE":               {"oci_service": "NoSQL Database",                   "oci_resource": "oci_nosql_table",                      "category": "NoSQL",          "confidence": 0.80, "migration_effort": "high"},
    "BIGTABLE":                {"oci_service": "NoSQL Database",                   "oci_resource": "oci_nosql_table",                      "category": "NoSQL",          "confidence": 0.75, "migration_effort": "high"},
    "BIGQUERY":                {"oci_service": "Autonomous Data Warehouse (ADW)",  "oci_resource": "oci_database_autonomous_database",     "category": "Analytics",      "confidence": 0.83, "migration_effort": "high"},
    "CLOUD MEMORYSTORE":       {"oci_service": "OCI Cache (Redis)",                "oci_resource": "oci_redis_redis_cluster",              "category": "Cache",          "confidence": 0.92, "migration_effort": "low"},
    "VPC":                     {"oci_service": "Virtual Cloud Network (VCN)",      "oci_resource": "oci_core_vcn",                         "category": "Networking",     "confidence": 0.97, "migration_effort": "low"},
    "CLOUD LOAD BALANCING":    {"oci_service": "Load Balancer (Flexible)",         "oci_resource": "oci_load_balancer_load_balancer",      "category": "Load Balancing", "confidence": 0.90, "migration_effort": "low"},
    "CLOUD DNS":               {"oci_service": "DNS",                              "oci_resource": "oci_dns_zone",                         "category": "DNS",            "confidence": 0.92, "migration_effort": "low"},
    "CLOUD CDN":               {"oci_service": "WAF + CDN (Akamai)",               "oci_resource": "oci_waf_web_app_firewall",             "category": "CDN",            "confidence": 0.78, "migration_effort": "medium"},
    "CLOUD INTERCONNECT":      {"oci_service": "FastConnect",                      "oci_resource": "oci_core_virtual_circuit",             "category": "Connectivity",   "confidence": 0.92, "migration_effort": "medium"},
    "CLOUD IAM":               {"oci_service": "OCI IAM",                          "oci_resource": "oci_identity_policy",                  "category": "Identity",       "confidence": 0.90, "migration_effort": "medium"},
    "CLOUD KMS":               {"oci_service": "Vault (Key Management)",           "oci_resource": "oci_kms_vault",                        "category": "Security",       "confidence": 0.93, "migration_effort": "low"},
    "CLOUD MONITORING":        {"oci_service": "OCI Monitoring",                   "oci_resource": "oci_monitoring_alarm",                 "category": "Monitoring",     "confidence": 0.87, "migration_effort": "medium"},
    "CLOUD LOGGING":           {"oci_service": "OCI Logging",                      "oci_resource": "oci_logging_log_group",                "category": "Logging",        "confidence": 0.88, "migration_effort": "medium"},
    "PUBSUB":                  {"oci_service": "OCI Streaming",                    "oci_resource": "oci_streaming_stream",                 "category": "Messaging",      "confidence": 0.85, "migration_effort": "medium"},
    "CLOUD TASKS":             {"oci_service": "OCI Queue",                        "oci_resource": "oci_queue_queue",                      "category": "Messaging",      "confidence": 0.82, "migration_effort": "medium"},
    "DATAFLOW":                {"oci_service": "OCI Data Flow (Apache Spark)",     "oci_resource": "oci_dataflow_application",             "category": "Data Processing","confidence": 0.82, "migration_effort": "medium"},
    "DATAPROC":                {"oci_service": "OCI Big Data Service (BDS)",       "oci_resource": "oci_bds_bds_instance",                 "category": "Big Data",       "confidence": 0.83, "migration_effort": "high"},
    "LOOKER":                  {"oci_service": "Oracle Analytics Cloud (OAC)",     "oci_resource": "oci_analytics_analytics_instance",     "category": "Analytics",      "confidence": 0.75, "migration_effort": "high"},
    "CLOUD BUILD":             {"oci_service": "OCI DevOps (Build Pipeline)",      "oci_resource": "oci_devops_build_pipeline",            "category": "DevOps",         "confidence": 0.82, "migration_effort": "medium"},
    "ARTIFACT REGISTRY":       {"oci_service": "Container Registry (OCIR)",        "oci_resource": "oci_artifacts_container_repository",   "category": "Containers",     "confidence": 0.90, "migration_effort": "low"},
    "CLOUD ARMOR":             {"oci_service": "WAF",                              "oci_resource": "oci_waf_web_app_firewall",             "category": "Security",       "confidence": 0.85, "migration_effort": "low"},
    "SECRET MANAGER":          {"oci_service": "Vault Secrets",                    "oci_resource": "oci_vault_secret",                     "category": "Security",       "confidence": 0.92, "migration_effort": "low"},
    "DEPLOYMENT MANAGER":      {"oci_service": "OCI Resource Manager (Terraform)", "oci_resource": "oci_resourcemanager_stack",            "category": "IaC",            "confidence": 0.82, "migration_effort": "high"},
}

# Unified lookup
_ALL_MAPPINGS = {"AWS": AWS_TO_OCI, "AZURE": AZURE_TO_OCI, "GCP": GCP_TO_OCI}


class MappingServer:
    SERVER_NAME = "mapping"
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
    def _normalise(self, service: str) -> str:
        return service.upper().replace("AMAZON ", "").replace("AWS ", "").replace("GOOGLE ", "").strip()

    # ------------------------------------------------------------------
    def map_service(
        self,
        source_service: str,
        source_provider: str = "AWS",
    ) -> Dict[str, Any]:
        """Map a single source service to its OCI equivalent."""
        t0 = time.time()
        provider = source_provider.upper()
        key = self._normalise(source_service)
        table = _ALL_MAPPINGS.get(provider, AWS_TO_OCI)

        mapping = table.get(key)
        if not mapping:
            # Try partial match
            for k, v in table.items():
                if key in k or k in key:
                    mapping = v
                    break

        if mapping:
            result = {
                "source_service": source_service,
                "source_provider": source_provider,
                "found": True,
                **mapping,
            }
        else:
            result = {
                "source_service": source_service,
                "source_provider": source_provider,
                "found": False,
                "oci_service": f"Manual assessment required for '{source_service}'",
                "oci_resource": "unknown",
                "category": "Unknown",
                "confidence": 0.30,
                "migration_effort": "high",
                "notes": "Service not in automated mapping table — architect review needed.",
            }

        self._record((time.time() - t0) * 1000)
        return result

    # ------------------------------------------------------------------
    # Legacy compatibility alias
    def aws_to_oci(self, aws_service: str) -> Dict[str, Any]:
        return self.map_service(aws_service, "AWS")

    # ------------------------------------------------------------------
    def bulk_map(
        self,
        services: List[str],
        source_provider: str = "AWS",
    ) -> Dict[str, Any]:
        """Map a list of source services to OCI equivalents."""
        mappings = [self.map_service(s, source_provider) for s in services]
        auto_mapped   = sum(1 for m in mappings if m.get("confidence", 0) >= 0.80)
        high_conf     = sum(1 for m in mappings if m.get("confidence", 0) >= 0.90)
        manual_review = len(mappings) - auto_mapped

        return {
            "source_provider": source_provider,
            "mappings": mappings,
            "total": len(mappings),
            "auto_mapped": auto_mapped,
            "high_confidence": high_conf,
            "manual_review_required": manual_review,
            "avg_confidence": round(
                sum(m.get("confidence", 0) for m in mappings) / max(len(mappings), 1), 3
            ),
        }

    # Legacy alias
    def bulk_aws_to_oci(self, services: List[str]) -> Dict[str, Any]:
        return self.bulk_map(services, "AWS")

    # ------------------------------------------------------------------
    def list_categories(self, source_provider: str = "AWS") -> Dict[str, Any]:
        """List all service categories for a provider."""
        table = _ALL_MAPPINGS.get(source_provider.upper(), AWS_TO_OCI)
        from collections import defaultdict
        by_cat: Dict[str, List[str]] = defaultdict(list)
        for svc, m in table.items():
            by_cat[m["category"]].append(svc)
        return {
            "source_provider": source_provider,
            "categories": dict(by_cat),
            "total_services": len(table),
        }

    # ------------------------------------------------------------------
    def get_oci_services(self) -> Dict[str, Any]:
        """Return unique OCI services referenced across all mappings."""
        seen = {}
        for table in _ALL_MAPPINGS.values():
            for m in table.values():
                svc = m["oci_service"]
                res = m["oci_resource"]
                if svc not in seen:
                    seen[svc] = {"oci_service": svc, "oci_resource": res, "category": m["category"]}
        return {"oci_services": list(seen.values()), "count": len(seen)}

    # ------------------------------------------------------------------
    def get_health_metrics(self) -> Dict[str, Any]:
        avg = self._total_latency_ms / max(self._call_count, 1)
        return {
            "server": self.SERVER_NAME,
            "version": self.VERSION,
            "total_calls": self._call_count,
            "success_rate": round(self._success_count / max(self._call_count, 1), 4),
            "avg_latency_ms": round(avg, 2),
            "status": "healthy",
            "aws_services": len(AWS_TO_OCI),
            "azure_services": len(AZURE_TO_OCI),
            "gcp_services": len(GCP_TO_OCI),
        }


mapping_server = MappingServer()
