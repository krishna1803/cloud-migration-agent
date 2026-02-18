"""MCP Server 7: OCI Cost Estimation (pricing).

Real OCI pricing data sourced from Oracle Cloud Price List (2024/2025).
Covers: Compute, Database, Storage, Networking, Functions, Security, Analytics.
Reference: https://www.oracle.com/cloud/price-list/
"""
import time
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# OCI COMPUTE PRICING — Pay-As-You-Go (USD)
# Source: https://www.oracle.com/cloud/price-list/#compute
# ---------------------------------------------------------------------------
OCI_COMPUTE_SHAPES: Dict[str, Dict] = {
    # AMD EPYC Milan — General Purpose Flex
    "VM.Standard.E4.Flex": {
        "processor": "AMD EPYC Milan", "arch": "x86_64",
        "per_ocpu_hour": 0.025, "per_gb_ram_hour": 0.0015,
        "max_ocpu": 64, "max_gb_ram": 1024,
        "network_gbps": 40, "storage": "NVMe SSD",
        "description": "Flexible AMD EPYC Milan VM — best price/performance for general workloads",
    },
    # AMD EPYC Genoa — General Purpose Flex (newer generation)
    "VM.Standard.E5.Flex": {
        "processor": "AMD EPYC Genoa", "arch": "x86_64",
        "per_ocpu_hour": 0.025, "per_gb_ram_hour": 0.0015,
        "max_ocpu": 94, "max_gb_ram": 1049,
        "network_gbps": 50,
        "description": "Flexible AMD EPYC Genoa VM — latest generation AMD",
    },
    # Intel Xeon Ice Lake — General Purpose Flex
    "VM.Standard3.Flex": {
        "processor": "Intel Xeon Ice Lake", "arch": "x86_64",
        "per_ocpu_hour": 0.025, "per_gb_ram_hour": 0.0015,
        "max_ocpu": 32, "max_gb_ram": 512,
        "network_gbps": 32,
        "description": "Flexible Intel Xeon Ice Lake VM",
    },
    # ARM Ampere A1 — Most cost-effective
    "VM.Standard.A1.Flex": {
        "processor": "Ampere A1 (ARM)", "arch": "aarch64",
        "per_ocpu_hour": 0.01, "per_gb_ram_hour": 0.0015,
        "max_ocpu": 80, "max_gb_ram": 512,
        "network_gbps": 32,
        "description": "ARM Ampere A1 Flex — lowest cost, ideal for cloud-native workloads",
    },
    # Intel Ice Lake High-Frequency — Compute Optimized
    "VM.Optimized3.Flex": {
        "processor": "Intel Xeon Ice Lake (3.0 GHz boost)", "arch": "x86_64",
        "per_ocpu_hour": 0.0425, "per_gb_ram_hour": 0.0025,
        "max_ocpu": 18, "max_gb_ram": 256,
        "network_gbps": 20,
        "description": "High-frequency Intel Flex for compute-intensive workloads",
    },
    # Bare Metal — AMD E4 128 OCPUs
    "BM.Standard.E4.128": {
        "processor": "AMD EPYC Milan", "arch": "x86_64",
        "flat_rate_hour": 2.976,
        "ocpu": 128, "gb_ram": 2048,
        "network_gbps": 100, "local_storage_tb": 6.8,
        "description": "128-OCPU AMD EPYC bare metal — dedicated host",
    },
    # Bare Metal — ARM A1 160 OCPUs
    "BM.Standard.A1.160": {
        "processor": "Ampere A1 (ARM)", "arch": "aarch64",
        "flat_rate_hour": 1.52,
        "ocpu": 160, "gb_ram": 1024,
        "network_gbps": 2 * 50,
        "description": "160-OCPU ARM Ampere A1 bare metal",
    },
    # GPU — A100 Bare Metal
    "BM.GPU4.8": {
        "processor": "Intel Xeon + 8×NVIDIA A100 80GB", "arch": "x86_64",
        "flat_rate_hour": 32.0,
        "ocpu": 64, "gb_ram": 2048, "gpu_count": 8, "gpu_model": "A100 80GB",
        "description": "8×A100 GPU bare metal for AI/ML training",
    },
    # GPU — A10 4 cards
    "BM.GPU.A10.4": {
        "processor": "Intel Xeon + 4×NVIDIA A10", "arch": "x86_64",
        "flat_rate_hour": 4.0,
        "ocpu": 64, "gb_ram": 1024, "gpu_count": 4, "gpu_model": "A10 24GB",
        "description": "4×A10 GPU bare metal for inference and AI workloads",
    },
}

# ---------------------------------------------------------------------------
# OCI DATABASE PRICING — USD
# Source: https://www.oracle.com/cloud/price-list/#database
# ---------------------------------------------------------------------------
OCI_DATABASE_PRICING: Dict[str, Dict] = {
    # Autonomous Database Serverless (OLTP / ATPS)
    "Autonomous Database OLTP": {
        "per_ocpu_hour": 0.2722,
        "storage_per_tb_month": 25.50,
        "min_ocpu": 1, "max_ocpu": 128,
        "description": "ATP Serverless — self-managing, self-securing OLTP DB",
        "notes": "Billing paused when stopped; auto-scaling available",
    },
    # Autonomous Data Warehouse (ADW)
    "Autonomous Data Warehouse": {
        "per_ocpu_hour": 0.2722,
        "storage_per_tb_month": 25.50,
        "min_ocpu": 1, "max_ocpu": 128,
        "description": "ADW Serverless — managed analytics/data warehouse",
    },
    # MySQL HeatWave
    "MySQL HeatWave": {
        "per_ocpu_hour": 0.025,       # same as E4.Flex compute
        "per_gb_ram_hour": 0.0015,
        "storage_per_gb_month": 0.0425,
        "heatwave_node_hour": 0.025,  # per HeatWave cluster node/hr
        "description": "Fully managed MySQL with in-memory analytics (HeatWave)",
    },
    # Oracle Base Database — Standard Edition 2
    "Oracle Database SE2": {
        "per_ocpu_hour": 0.1068,
        "storage_per_gb_month": 0.0425,
        "description": "Oracle DB Standard Edition 2 on VM/BM",
    },
    # Oracle Base Database — Enterprise Edition
    "Oracle Database EE": {
        "per_ocpu_hour": 0.4744,
        "storage_per_gb_month": 0.0425,
        "description": "Oracle DB Enterprise Edition on VM/BM",
    },
    # Oracle Base Database — Enterprise Edition High Performance
    "Oracle Database EE HP": {
        "per_ocpu_hour": 0.6449,
        "storage_per_gb_month": 0.0425,
        "description": "Oracle DB EE High Performance (includes all options)",
    },
    # NoSQL Database — OCI NoSQL
    "OCI NoSQL": {
        "read_units_per_million": 0.0228,
        "write_units_per_million": 0.114,
        "storage_per_gb_month": 0.025,
        "description": "Serverless NoSQL — pay per operation and storage",
    },
    # Cache with Redis
    "OCI Cache (Redis)": {
        "per_gb_hour": 0.0018,
        "description": "Managed Redis-compatible in-memory cache",
    },
}

# ---------------------------------------------------------------------------
# OCI STORAGE PRICING — USD per GB/month
# Source: https://www.oracle.com/cloud/price-list/#storage
# ---------------------------------------------------------------------------
OCI_STORAGE_PRICING: Dict[str, Dict] = {
    "Object Storage Standard": {
        "per_gb_month": 0.0255,
        "requests_per_10k": 0.00,   # first 50K free, then tiered
        "description": "Durable object store — S3-compatible, 11 nines durability",
    },
    "Object Storage Infrequent Access": {
        "per_gb_month": 0.01,
        "retrieval_per_gb": 0.01,
        "description": "Lower cost tier for infrequently accessed data",
    },
    "Archive Storage": {
        "per_gb_month": 0.0026,
        "restore_per_gb": 0.003,
        "min_retention_days": 90,
        "description": "Cold archive storage — lowest cost, 4-24 hr restore",
    },
    "Block Volume": {
        "per_gb_month": 0.0255,
        "performance_unit_per_vpu_gb_month": 0.0017,
        "description": "Persistent SAN-attached block storage; VPU adjusts IOPS",
        "notes": "Default 10 VPU/GB = ~2000 IOPS/TB. Max 120 VPU/GB (Ultra High).",
    },
    "Block Volume Ultra High": {
        "per_gb_month": 0.0255,
        "performance_unit_per_vpu_gb_month": 0.0017,
        "vpu": 120,
        "description": "Block Volume at Ultra High Performance (120 VPU)",
    },
    "File Storage": {
        "per_gb_month": 0.07,
        "snapshot_per_gb_month": 0.03,
        "description": "NFS-compatible shared file system",
    },
}

# ---------------------------------------------------------------------------
# OCI NETWORKING PRICING — USD
# Source: https://www.oracle.com/cloud/price-list/#networking
# ---------------------------------------------------------------------------
OCI_NETWORKING_PRICING: Dict[str, Any] = {
    "VCN": {"monthly": 0.0, "description": "Virtual Cloud Network — free"},
    "Internet Gateway": {"monthly": 0.0, "description": "Internet Gateway — free"},
    "NAT Gateway": {"per_hour": 0.045, "per_gb": 0.0, "description": "NAT Gateway for outbound internet traffic"},
    "Service Gateway": {"monthly": 0.0, "description": "OCI Service Gateway — free"},
    "Dynamic Routing Gateway": {"monthly": 0.0, "description": "DRG — free"},
    "Load Balancer Flexible": {
        "per_hour": 0.025,
        "per_gb_processed": 0.008,
        "min_bandwidth_mbps": 10,
        "max_bandwidth_mbps": 8000,
        "description": "Flexible L7 load balancer",
    },
    "Network Load Balancer": {
        "per_hour": 0.008,
        "per_gb_processed": 0.004,
        "description": "L4 network load balancer — lower cost, higher throughput",
    },
    "FastConnect 1Gbps": {
        "monthly": 72.65,
        "description": "Dedicated private connectivity to OCI — 1 Gbps circuit",
    },
    "FastConnect 10Gbps": {
        "monthly": 726.50,
        "description": "Dedicated private connectivity to OCI — 10 Gbps circuit",
    },
    "Data Transfer Out (Internet)": {
        "first_10tb_per_gb": 0.0085,
        "next_40tb_per_gb": 0.0051,
        "over_150tb_per_gb": 0.0026,
        "description": "Egress to internet; inbound always free",
    },
    "Data Transfer Between Regions": {
        "per_gb": 0.02,
        "description": "Cross-region data transfer",
    },
    "Bastion Service": {
        "per_session_hour": 0.0,
        "description": "Managed bastion (SSH jump host) — free",
    },
}

# ---------------------------------------------------------------------------
# OCI SECURITY PRICING — USD
# ---------------------------------------------------------------------------
OCI_SECURITY_PRICING: Dict[str, Dict] = {
    "Vault (Virtual)": {
        "per_key_version_month": 0.35,
        "per_crypto_op_10k": 0.03,
        "description": "Software-protected key management vault",
    },
    "Vault (HSM)": {
        "per_hsm_partition_month": 1000.0,
        "per_crypto_op_10k": 0.03,
        "description": "Hardware Security Module dedicated partition",
    },
    "Web Application Firewall": {
        "per_policy_hour": 0.025,
        "per_million_requests": 0.60,
        "description": "OCI WAF — managed L7 firewall",
    },
    "Cloud Guard": {
        "monthly": 0.0,
        "description": "Cloud Guard basic — free security posture management",
    },
    "Security Zones": {
        "monthly": 0.0,
        "description": "Security Zones — free enforced security posture",
    },
    "Certificates Service": {
        "per_cert_month": 0.0,
        "description": "OCI Certificates (TLS) — free for OCI-issued",
    },
}

# ---------------------------------------------------------------------------
# OCI SERVERLESS / FUNCTIONS PRICING — USD
# ---------------------------------------------------------------------------
OCI_FUNCTIONS_PRICING: Dict[str, Any] = {
    "OCI Functions": {
        "per_gb_second": 0.00001417,
        "per_million_calls": 0.40,
        "free_tier_gb_seconds_month": 400_000,
        "free_tier_calls_month": 2_000_000,
        "description": "Serverless functions — pay per invocation and duration",
    },
    "API Gateway": {
        "per_million_calls": 0.0,    # Free for first 1M/month
        "over_1m_per_million": 3.00,
        "description": "Managed REST/WebSocket API gateway",
    },
    "OCI Queue": {
        "per_million_requests": 0.0,  # Free tier generous
        "per_gb_month": 0.0023,
        "description": "Managed message queue service",
    },
    "OCI Notifications (ONS)": {
        "per_million_https_deliveries": 0.60,
        "per_million_email_deliveries": 0.0,
        "description": "Pub/sub notification service",
    },
    "OCI Streaming": {
        "per_mb_put": 0.000285,
        "per_mb_get": 0.00085,
        "per_partition_hour": 0.085,
        "description": "Apache Kafka-compatible streaming (partitions)",
    },
}

# ---------------------------------------------------------------------------
# OCI CONTAINER / KUBERNETES PRICING
# ---------------------------------------------------------------------------
OCI_CONTAINER_PRICING: Dict[str, Dict] = {
    "OKE Control Plane": {
        "monthly": 0.0,
        "description": "Oracle Container Engine for Kubernetes control plane — free",
    },
    "OKE Worker Nodes": {
        "note": "Billed as standard compute shapes",
        "description": "OKE worker nodes use standard OCI compute pricing",
    },
    "Container Registry (OCIR)": {
        "storage_per_gb_month": 0.0255,  # object storage rate
        "description": "OCI Container Image Registry (storage at OS rates)",
    },
}

# ---------------------------------------------------------------------------
# OCI ANALYTICS / AI PRICING
# ---------------------------------------------------------------------------
OCI_ANALYTICS_PRICING: Dict[str, Dict] = {
    "Oracle Analytics Cloud Professional": {
        "per_ocpu_hour": 0.16,
        "description": "OAC Professional — self-service BI",
    },
    "Oracle Analytics Cloud Enterprise": {
        "per_ocpu_hour": 0.34,
        "description": "OAC Enterprise — advanced analytics + ML",
    },
    "OCI Data Integration": {
        "per_ocpu_hour": 0.20,
        "description": "ETL / data pipeline service",
    },
    "OCI Generative AI": {
        "cohere_command_r_per_m_tokens_in": 0.50,
        "cohere_command_r_per_m_tokens_out": 1.50,
        "cohere_command_r_plus_per_m_tokens_in": 3.00,
        "cohere_command_r_plus_per_m_tokens_out": 15.00,
        "embed_per_m_tokens": 0.10,
        "description": "OCI Generative AI Service — LLM inference",
    },
    "Logging Analytics": {
        "per_gb_ingested": 2.50,
        "free_tier_gb_month": 10,
        "description": "Log management and analytics",
    },
    "OCI Monitoring": {
        "first_500m_datapoints": 0.0,
        "per_million_datapoints": 0.02,
        "description": "Custom metrics and alarms",
    },
}

# ---------------------------------------------------------------------------
# OCI REGION MULTIPLIERS (spot overrides; most regions same price)
# ---------------------------------------------------------------------------
REGION_PRICING_NOTES: Dict[str, str] = {
    "us-ashburn-1":    "Standard pricing (US East — Ashburn)",
    "us-phoenix-1":    "Standard pricing (US West — Phoenix)",
    "eu-frankfurt-1":  "Standard pricing (EU — Frankfurt)",
    "eu-amsterdam-1":  "Standard pricing (EU — Amsterdam)",
    "uk-london-1":     "Standard pricing (UK — London)",
    "ap-tokyo-1":      "Standard pricing (Asia Pacific — Tokyo)",
    "ap-sydney-1":     "Standard pricing (Asia Pacific — Sydney)",
    "ap-singapore-1":  "Standard pricing (Asia Pacific — Singapore)",
    "ap-mumbai-1":     "Standard pricing (India — Mumbai)",
    "me-jeddah-1":     "Standard pricing (Middle East — Jeddah)",
    "ca-toronto-1":    "Standard pricing (Canada — Toronto)",
    "sa-saopaulo-1":   "Standard pricing (Brazil — São Paulo)",
}


class PricingServer:
    SERVER_NAME = "pricing"
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
    # Public: Compute estimate
    # ------------------------------------------------------------------
    def estimate_compute(
        self,
        shape: str,
        ocpu: int = 2,
        memory_gb: int = 16,
        hours_per_month: int = 730,
        quantity: int = 1,
    ) -> Dict[str, Any]:
        """Estimate monthly compute cost for an OCI shape."""
        t0 = time.time()
        info = OCI_COMPUTE_SHAPES.get(shape)
        if not info:
            # Default to E4.Flex pricing
            info = OCI_COMPUTE_SHAPES["VM.Standard.E4.Flex"]
            shape = "VM.Standard.E4.Flex (default)"

        if "flat_rate_hour" in info:
            cost_per_month = info["flat_rate_hour"] * hours_per_month * quantity
            breakdown = {"flat_rate": round(cost_per_month, 2)}
        else:
            ocpu_cost  = ocpu * info["per_ocpu_hour"] * hours_per_month
            ram_cost   = memory_gb * info["per_gb_ram_hour"] * hours_per_month
            cost_per_month = (ocpu_cost + ram_cost) * quantity
            breakdown = {
                "ocpu": round(ocpu_cost * quantity, 2),
                "ram":  round(ram_cost  * quantity, 2),
            }

        self._record((time.time() - t0) * 1000)
        return {
            "shape": shape,
            "ocpu": ocpu,
            "memory_gb": memory_gb,
            "quantity": quantity,
            "hours_per_month": hours_per_month,
            "monthly_cost_usd": round(cost_per_month, 2),
            "annual_cost_usd":  round(cost_per_month * 12, 2),
            "breakdown": breakdown,
            "shape_info": {k: v for k, v in info.items()
                           if k not in ("per_ocpu_hour", "per_gb_ram_hour", "flat_rate_hour")},
        }

    # ------------------------------------------------------------------
    # Public: Storage estimate
    # ------------------------------------------------------------------
    def estimate_storage(
        self,
        storage_class: str,
        size_gb: float,
        vpu: int = 10,
    ) -> Dict[str, Any]:
        """Estimate monthly storage cost."""
        t0 = time.time()
        info = OCI_STORAGE_PRICING.get(storage_class)
        if not info:
            storage_class = "Object Storage Standard"
            info = OCI_STORAGE_PRICING[storage_class]

        base_cost = size_gb * info["per_gb_month"]
        extra_cost = 0.0

        if storage_class in ("Block Volume", "Block Volume Ultra High"):
            extra_cost = size_gb * vpu * info.get("performance_unit_per_vpu_gb_month", 0)
        elif storage_class == "File Storage":
            pass  # base already covers it

        total = base_cost + extra_cost
        self._record((time.time() - t0) * 1000)
        return {
            "storage_class": storage_class,
            "size_gb": size_gb,
            "monthly_cost_usd": round(total, 2),
            "annual_cost_usd":  round(total * 12, 2),
            "breakdown": {
                "base_storage": round(base_cost, 2),
                "performance_units": round(extra_cost, 2),
            },
            "description": info["description"],
        }

    # ------------------------------------------------------------------
    # Public: Database estimate
    # ------------------------------------------------------------------
    def estimate_database(
        self,
        db_service: str,
        ocpu: int = 2,
        storage_tb: float = 1.0,
        hours_per_month: int = 730,
    ) -> Dict[str, Any]:
        """Estimate monthly database cost."""
        t0 = time.time()
        info = OCI_DATABASE_PRICING.get(db_service)
        if not info:
            db_service = "Autonomous Database OLTP"
            info = OCI_DATABASE_PRICING[db_service]

        compute_cost = 0.0
        storage_cost = 0.0

        if "per_ocpu_hour" in info:
            compute_cost = ocpu * info["per_ocpu_hour"] * hours_per_month
        if "storage_per_tb_month" in info:
            storage_cost = storage_tb * info["storage_per_tb_month"]
        elif "storage_per_gb_month" in info:
            storage_cost = storage_tb * 1024 * info["storage_per_gb_month"]

        total = compute_cost + storage_cost
        self._record((time.time() - t0) * 1000)
        return {
            "db_service": db_service,
            "ocpu": ocpu,
            "storage_tb": storage_tb,
            "monthly_cost_usd": round(total, 2),
            "annual_cost_usd":  round(total * 12, 2),
            "breakdown": {
                "compute": round(compute_cost, 2),
                "storage": round(storage_cost, 2),
            },
            "description": info.get("description", ""),
            "notes":       info.get("notes", ""),
        }

    # ------------------------------------------------------------------
    # Public: Network estimate
    # ------------------------------------------------------------------
    def estimate_network(
        self,
        egress_gb_month: float = 0.0,
        num_flexible_lbs: int = 0,
        lb_data_gb_month: float = 0.0,
        num_nlbs: int = 0,
        nlb_data_gb_month: float = 0.0,
        fastconnect_gbps: int = 0,
    ) -> Dict[str, Any]:
        """Estimate monthly networking cost."""
        t0 = time.time()
        egress = OCI_NETWORKING_PRICING["Data Transfer Out (Internet)"]
        lb     = OCI_NETWORKING_PRICING["Load Balancer Flexible"]
        nlb    = OCI_NETWORKING_PRICING["Network Load Balancer"]
        fc1    = OCI_NETWORKING_PRICING["FastConnect 1Gbps"]

        # Egress tiers: 0-10TB, 10-50TB, 50-150TB, 150TB+
        first_10tb  = min(egress_gb_month, 10_000)
        next_40tb   = max(min(egress_gb_month - 10_000, 40_000), 0)
        over_150tb  = max(egress_gb_month - 150_000, 0)

        egress_cost = (
            first_10tb * egress["first_10tb_per_gb"]
            + next_40tb * egress["next_40tb_per_gb"]
            + over_150tb * egress["over_150tb_per_gb"]
        )
        flb_cost  = num_flexible_lbs * lb["per_hour"] * 730 + lb_data_gb_month * lb["per_gb_processed"]
        nlb_cost  = num_nlbs * nlb["per_hour"] * 730 + nlb_data_gb_month * nlb["per_gb_processed"]
        fc_cost   = fastconnect_gbps * fc1["monthly"]   # approximate 1Gbps per unit

        total = egress_cost + flb_cost + nlb_cost + fc_cost
        self._record((time.time() - t0) * 1000)
        return {
            "monthly_cost_usd": round(total, 2),
            "annual_cost_usd":  round(total * 12, 2),
            "breakdown": {
                "egress_internet": round(egress_cost, 2),
                "load_balancers":  round(flb_cost, 2),
                "network_lbs":     round(nlb_cost, 2),
                "fastconnect":     round(fc_cost, 2),
            },
        }

    # ------------------------------------------------------------------
    # Public: Full resource list estimate (for migration sizing)
    # ------------------------------------------------------------------
    def oci_estimate(self, resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Estimate total monthly/annual cost from a list of resource descriptors.

        Each resource dict may contain:
          type: 'compute' | 'storage' | 'database' | 'load_balancer' | 'network' | 'functions'
          Plus type-specific fields (shape, ocpu, memory_gb, size_gb, etc.)
        """
        t0 = time.time()
        line_items = []
        total_monthly = 0.0

        for r in resources:
            rtype = r.get("type", "").lower()
            qty   = r.get("quantity", 1)
            name  = r.get("name", rtype)

            try:
                if rtype == "compute":
                    shape     = r.get("shape", "VM.Standard.E4.Flex")
                    ocpu      = r.get("ocpu", 2)
                    memory_gb = r.get("memory_gb", 16)
                    res = self.estimate_compute(shape, ocpu, memory_gb, quantity=qty)
                    cost = res["monthly_cost_usd"]
                    detail = res["breakdown"]

                elif rtype == "storage":
                    cls     = r.get("storage_class", "Object Storage Standard")
                    size_gb = r.get("size_gb", 100)
                    vpu     = r.get("vpu", 10)
                    res = self.estimate_storage(cls, size_gb * qty, vpu)
                    cost = res["monthly_cost_usd"]
                    detail = res["breakdown"]

                elif rtype == "database":
                    db_svc      = r.get("db_service", "Autonomous Database OLTP")
                    ocpu        = r.get("ocpu", 2)
                    storage_tb  = r.get("storage_tb", 1.0)
                    res = self.estimate_database(db_svc, ocpu, storage_tb)
                    cost = res["monthly_cost_usd"] * qty
                    detail = res["breakdown"]

                elif rtype == "load_balancer":
                    lb_type = r.get("lb_type", "flexible")
                    if lb_type == "network":
                        cost = qty * OCI_NETWORKING_PRICING["Network Load Balancer"]["per_hour"] * 730
                    else:
                        cost = qty * OCI_NETWORKING_PRICING["Load Balancer Flexible"]["per_hour"] * 730
                    detail = {"load_balancer": round(cost, 2)}

                elif rtype == "functions":
                    gb_seconds = r.get("gb_seconds_month", 0)
                    calls_m    = r.get("million_calls_month", 0)
                    fp = OCI_FUNCTIONS_PRICING["OCI Functions"]
                    billable_gbs = max(gb_seconds - fp["free_tier_gb_seconds_month"], 0)
                    cost = billable_gbs * fp["per_gb_second"] + calls_m * fp["per_million_calls"]
                    detail = {"functions_compute": round(cost, 2)}

                elif rtype == "nat_gateway":
                    cost = qty * OCI_NETWORKING_PRICING["NAT Gateway"]["per_hour"] * 730
                    detail = {"nat_gateway": round(cost, 2)}

                else:
                    cost = r.get("estimated_monthly_cost", 0.0) * qty
                    detail = {"manual_estimate": round(cost, 2)}

            except Exception as exc:
                cost = r.get("estimated_monthly_cost", 0.0)
                detail = {"error": str(exc)}

            total_monthly += cost
            line_items.append({
                "name": name,
                "type": rtype,
                "quantity": qty,
                "monthly_cost_usd": round(cost, 2),
                "detail": detail,
            })

        self._record((time.time() - t0) * 1000)
        return {
            "line_items": line_items,
            "total_monthly_cost_usd": round(total_monthly, 2),
            "total_annual_cost_usd":  round(total_monthly * 12, 2),
            "currency": "USD",
            "pricing_model": "OCI Pay-As-You-Go (2024/2025)",
            "note": "Estimates based on public OCI price list. Committed-use / UCC discounts not applied.",
        }

    # ------------------------------------------------------------------
    # Public: Source vs OCI ROI comparison
    # ------------------------------------------------------------------
    def compare_with_source(
        self,
        source_monthly_cost: float,
        oci_monthly_cost: float,
        migration_cost_usd: float = 0.0,
        payback_months: int = 36,
    ) -> Dict[str, Any]:
        """Savings analysis: current vs OCI, including migration ROI."""
        savings_monthly  = source_monthly_cost - oci_monthly_cost
        savings_annual   = savings_monthly * 12
        savings_pct      = savings_monthly / max(source_monthly_cost, 1) * 100
        roi_months       = (migration_cost_usd / savings_monthly) if savings_monthly > 0 else float("inf")
        total_savings_3y = savings_annual * 3 - migration_cost_usd

        return {
            "source_monthly_cost_usd":  round(source_monthly_cost, 2),
            "oci_monthly_cost_usd":     round(oci_monthly_cost, 2),
            "monthly_savings_usd":      round(savings_monthly, 2),
            "annual_savings_usd":       round(savings_annual, 2),
            "savings_percentage":       round(savings_pct, 1),
            "migration_cost_usd":       round(migration_cost_usd, 2),
            "payback_months":           round(roi_months, 1),
            "net_savings_3yr_usd":      round(total_savings_3y, 2),
            "recommendation": (
                "Excellent ROI — proceed with migration"
                if savings_pct >= 30
                else "Moderate savings — evaluate non-cost benefits (reliability, security)"
                if savings_pct >= 10
                else "Low direct cost savings — assess total-value factors"
            ),
        }

    # ------------------------------------------------------------------
    # Public: List available shapes / services
    # ------------------------------------------------------------------
    def list_compute_shapes(self) -> Dict[str, Any]:
        """Return all available OCI compute shapes with pricing."""
        return {"shapes": OCI_COMPUTE_SHAPES, "count": len(OCI_COMPUTE_SHAPES)}

    def list_database_services(self) -> Dict[str, Any]:
        """Return all available OCI database services."""
        return {"services": OCI_DATABASE_PRICING, "count": len(OCI_DATABASE_PRICING)}

    def list_storage_classes(self) -> Dict[str, Any]:
        """Return all OCI storage classes."""
        return {"classes": OCI_STORAGE_PRICING, "count": len(OCI_STORAGE_PRICING)}

    def get_region_info(self, region: str) -> Dict[str, Any]:
        """Return pricing note for a given OCI region."""
        note = REGION_PRICING_NOTES.get(region, "Standard pricing applies")
        return {"region": region, "note": note, "available_regions": list(REGION_PRICING_NOTES.keys())}

    # ------------------------------------------------------------------
    def get_health_metrics(self) -> Dict[str, Any]:
        avg_latency = self._total_latency_ms / max(self._call_count, 1)
        return {
            "server": self.SERVER_NAME,
            "version": self.VERSION,
            "total_calls": self._call_count,
            "success_rate": round(self._success_count / max(self._call_count, 1), 4),
            "avg_latency_ms": round(avg_latency, 2),
            "status": "healthy",
            "data_source": "Oracle Cloud Price List 2024/2025",
        }


pricing_server = PricingServer()
