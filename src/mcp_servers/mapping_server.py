"""MCP Server 4: Service Mapping (mapping)."""
import time
from typing import Any, Dict, List, Optional

AWS_TO_OCI_MAPPING = {
    "EC2":        {"oci_service": "Compute Instance",                           "oci_resource": "oci_core_instance",                    "category": "Compute",        "confidence": 0.95},
    "LAMBDA":     {"oci_service": "OCI Functions",                              "oci_resource": "oci_functions_function",               "category": "Serverless",     "confidence": 0.92},
    "EKS":        {"oci_service": "Oracle Container Engine for Kubernetes (OKE)","oci_resource": "oci_containerengine_cluster",          "category": "Kubernetes",     "confidence": 0.95},
    "S3":         {"oci_service": "Object Storage",                             "oci_resource": "oci_objectstorage_bucket",             "category": "Object Storage", "confidence": 0.98},
    "EBS":        {"oci_service": "Block Volume",                               "oci_resource": "oci_core_volume",                      "category": "Block Storage",  "confidence": 0.95},
    "RDS":        {"oci_service": "MySQL HeatWave / Autonomous Database",       "oci_resource": "oci_mysql_mysql_db_system",            "category": "Database",       "confidence": 0.90},
    "VPC":        {"oci_service": "Virtual Cloud Network (VCN)",                "oci_resource": "oci_core_vcn",                         "category": "Networking",     "confidence": 0.99},
    "ELB":        {"oci_service": "Load Balancer",                              "oci_resource": "oci_load_balancer_load_balancer",      "category": "Load Balancing", "confidence": 0.95},
    "IAM":        {"oci_service": "Identity and Access Management",             "oci_resource": "oci_identity_policy",                  "category": "Identity",       "confidence": 0.97},
    "CLOUDWATCH": {"oci_service": "Monitoring & Logging",                       "oci_resource": "oci_monitoring_alarm",                 "category": "Monitoring",     "confidence": 0.88},
    "SNS":        {"oci_service": "OCI Notifications",                          "oci_resource": "oci_ons_notification_topic",           "category": "Notifications",  "confidence": 0.88},
    "SQS":        {"oci_service": "OCI Queue",                                  "oci_resource": "oci_queue_queue",                      "category": "Queuing",        "confidence": 0.88},
    "DYNAMODB":   {"oci_service": "NoSQL Database",                             "oci_resource": "oci_nosql_table",                      "category": "NoSQL",          "confidence": 0.90},
    "ROUTE53":    {"oci_service": "DNS",                                        "oci_resource": "oci_dns_zone",                         "category": "DNS",            "confidence": 0.92},
    "KMS":        {"oci_service": "Vault (Key Management)",                     "oci_resource": "oci_kms_vault",                        "category": "Security",       "confidence": 0.93},
}


class MappingServer:
    SERVER_NAME = "mapping"
    VERSION = "1.0.0"

    def __init__(self):
        self._call_count = 0
        self._success_count = 0
        self._total_latency_ms = 0

    def _record_call(self, latency_ms: float, success: bool = True):
        self._call_count += 1
        if success: self._success_count += 1
        self._total_latency_ms += latency_ms

    def aws_to_oci(self, aws_service: str) -> Dict[str, Any]:
        start = time.time()
        service_upper = aws_service.upper().replace("AMAZON ", "").replace("AWS ", "")
        mapping = AWS_TO_OCI_MAPPING.get(service_upper)
        if mapping:
            result = {"source_service": aws_service, "source_provider": "AWS", **mapping}
        else:
            result = {"source_service": aws_service, "source_provider": "AWS", "oci_service": f"OCI equivalent for {aws_service}", "confidence": 0.50, "note": "Manual mapping required"}
        self._record_call((time.time() - start) * 1000)
        return result

    def bulk_aws_to_oci(self, services: List[str]) -> Dict[str, Any]:
        mappings = [self.aws_to_oci(s) for s in services]
        mapped = sum(1 for m in mappings if m.get("confidence", 0) >= 0.80)
        return {"mappings": mappings, "total": len(mappings), "auto_mapped": mapped, "manual_review_required": len(mappings) - mapped}

    def get_health_metrics(self) -> Dict[str, Any]:
        return {"server": self.SERVER_NAME, "total_calls": self._call_count, "success_rate": self._success_count / max(self._call_count, 1), "avg_latency_ms": 0, "status": "healthy"}


mapping_server = MappingServer()
