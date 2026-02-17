"""MCP Server 1: Knowledge Base (kb) - Oracle 23ai Vector DB with RAG."""
import time
import random
from typing import Any, Dict, List, Optional
from datetime import datetime


class KBServer:
    """Knowledge Base MCP Server."""
    SERVER_NAME = "kb"
    VERSION = "1.0.0"

    def __init__(self):
        self.collections = ["service_mappings", "best_practices", "architecture_patterns", "pricing_info", "compliance_standards"]
        self._call_count = 0
        self._success_count = 0
        self._total_latency_ms = 0

    def _record_call(self, latency_ms: float, success: bool = True):
        self._call_count += 1
        if success:
            self._success_count += 1
        self._total_latency_ms += latency_ms

    def query(self, query_text: str, collection: str = "all", top_k: int = 5, migration_context=None) -> Dict[str, Any]:
        start = time.time()
        results = [
            {"document_id": f"doc_{collection}_{i+1}", "content": f"Relevant content for {query_text!r} from {collection}.",
             "relevance_score": round(0.95 - (i * 0.1), 2), "source": f"{collection}/document_{i+1}.md",
             "metadata": {"collection": collection}}
            for i in range(min(top_k, 3))
        ]
        answer = f"Based on the Oracle Cloud migration knowledge base: {query_text} - OCI provides equivalent services."
        latency = (time.time() - start) * 1000
        self._record_call(latency)
        return {"answer": answer, "retrieved_documents": results, "collection": collection, "query": query_text, "latency_ms": round(latency, 2)}

    def search(self, query_text: str, collection: str = "all") -> Dict[str, Any]:
        results = [{"id": f"result_{i}", "title": f"Result {i} for {query_text!r}", "collection": collection, "score": round(0.9 - (i * 0.05), 2)} for i in range(5)]
        return {"results": results, "total": len(results)}

    def add_document(self, content: str, collection: str, metadata=None, source: str = "user") -> Dict[str, Any]:
        doc_id = f"doc_{int(time.time())}_{random.randint(1000, 9999)}"
        return {"document_id": doc_id, "collection": collection, "status": "indexed", "chunks_created": max(1, len(content) // 500)}

    def query_service_mapping(self, source_service: str, source_provider: str) -> Dict[str, Any]:
        mappings = {
            "EC2": {"oci_service": "Compute Instance", "confidence": 0.95},
            "S3": {"oci_service": "Object Storage", "confidence": 0.98},
            "RDS": {"oci_service": "MySQL HeatWave / Autonomous Database", "confidence": 0.90},
            "VPC": {"oci_service": "Virtual Cloud Network (VCN)", "confidence": 0.99},
            "LAMBDA": {"oci_service": "OCI Functions", "confidence": 0.92},
            "EKS": {"oci_service": "Oracle Container Engine for Kubernetes (OKE)", "confidence": 0.95},
            "IAM": {"oci_service": "Identity and Access Management (IAM)", "confidence": 0.97},
            "ELB": {"oci_service": "Load Balancer", "confidence": 0.95},
        }
        mapping = mappings.get(source_service.upper(), {"oci_service": f"OCI equivalent for {source_service}", "confidence": 0.70})
        return {"source_service": source_service, "source_provider": source_provider, "mapping": mapping}

    def query_best_practices(self, topic: str) -> Dict[str, Any]:
        return {"topic": topic, "practices": [{"practice": f"Best practice for {topic}", "priority": "high"}]}

    def query_architecture_patterns(self, pattern_type: str) -> Dict[str, Any]:
        return {"pattern_type": pattern_type, "patterns": [{"name": f"OCI {pattern_type} Pattern", "components": ["VCN", "Compute", "Load Balancer"]}]}

    def query_pricing_info(self, service_name: str, region: str = "us-ashburn-1") -> Dict[str, Any]:
        return {"service": service_name, "region": region, "pricing": {"note": "Contact Oracle for exact pricing"}}

    def query_compliance_standards(self, standard: str) -> Dict[str, Any]:
        return {"standard": standard, "oci_compliance": True, "certifications": ["SOC 2", "ISO 27001", "PCI DSS", "HIPAA"]}

    def list_collections(self) -> Dict[str, Any]:
        return {"collections": [{"name": c, "document_count": random.randint(50, 500)} for c in self.collections]}

    def get_health_metrics(self) -> Dict[str, Any]:
        avg_latency = self._total_latency_ms / max(self._call_count, 1)
        success_rate = self._success_count / max(self._call_count, 1)
        return {"server": self.SERVER_NAME, "total_calls": self._call_count, "success_rate": success_rate, "avg_latency_ms": round(avg_latency, 2), "status": "healthy"}


kb_server = KBServer()
