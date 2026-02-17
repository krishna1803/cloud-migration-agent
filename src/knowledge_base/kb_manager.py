"""
Knowledge Base Manager for Oracle 23ai Vector Database.
Provides document ingestion, embedding generation, and RAG queries.
"""

import hashlib
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from .collections import COLLECTIONS

logger = logging.getLogger(__name__)


class KnowledgeBaseManager:
    """Knowledge Base Manager with in-memory store (Oracle 23ai in production)."""

    def __init__(self, db_config=None, genai_config=None):
        self.db_config = db_config
        self.genai_config = genai_config
        self._document_store: Dict[str, Dict] = {}
        self._seed_baseline_knowledge()

    def _seed_baseline_knowledge(self):
        """Seed KB with baseline migration knowledge."""
        baseline_docs = [
            {"id": "map_001", "content": "AWS EC2 maps to OCI Compute Instance. EC2 instance types map to OCI shapes: t3/m5 -> VM.Standard.E4.Flex. OCI offers flexible shapes for right-sizing. 40% cost advantage with Ampere A1 ARM instances.", "collection": "service_mappings", "source": "oracle/service-mapping-guide"},
            {"id": "map_002", "content": "AWS S3 maps to OCI Object Storage. Features: bucket creation, versioning, lifecycle policies, server-side encryption, cross-region replication. OCI pricing: $0.0255/GB/month Standard, $0.0102/GB/month Infrequent Access.", "collection": "service_mappings", "source": "oracle/service-mapping-guide"},
            {"id": "map_003", "content": "AWS RDS PostgreSQL/MySQL maps to OCI MySQL HeatWave Service. RDS Oracle maps directly to OCI Oracle Database Cloud. HeatWave provides in-memory analytics acceleration at no additional cost.", "collection": "service_mappings", "source": "oracle/service-mapping-guide"},
            {"id": "map_004", "content": "AWS VPC maps to OCI Virtual Cloud Network (VCN). Subnets, route tables, internet gateways, NAT gateways, and security groups map to equivalent OCI constructs.", "collection": "service_mappings", "source": "oracle/networking-guide"},
            {"id": "map_005", "content": "AWS Lambda maps to OCI Functions. AWS EKS maps to Oracle Container Engine for Kubernetes (OKE). AWS DynamoDB maps to OCI NoSQL Database.", "collection": "service_mappings", "source": "oracle/service-mapping-guide"},
            {"id": "bp_001",  "content": "Migration best practice: Use 6-R framework (Rehost, Replatform, Repurchase, Refactor, Retire, Retain). Start with rehosting (lift-and-shift) then optimize. Always migrate stateless services first.", "collection": "best_practices", "source": "oracle/migration-best-practices"},
            {"id": "bp_002",  "content": "Network migration: Create VCN and networking first. Use Bastion service or VPN for admin access. Separate public/private subnets. Use NSGs for fine-grained control.", "collection": "best_practices", "source": "oracle/networking-best-practices"},
            {"id": "bp_003",  "content": "Database migration: Use Oracle Data Pump or OCI Database Migration Service. Enable Automatic Backups before migration. Test restore procedure before cutover.", "collection": "best_practices", "source": "oracle/database-migration-guide"},
            {"id": "bp_004",  "content": "Cost optimization: Use Annual Flex subscriptions for 33% discount. Use Ampere A1 ARM instances for 4x cost advantage. Enable autoscaling for variable workloads.", "collection": "best_practices", "source": "oracle/cost-optimization-guide"},
            {"id": "arch_001","content": "OCI Landing Zone: Foundation pattern using compartments for isolation, IAM policies for least privilege, VCN with public/private subnets, bastion host, security lists. Deployed via terraform-oci-open-lz.", "collection": "architecture_patterns", "source": "oracle/landing-zone-guide"},
            {"id": "arch_002","content": "Three-tier web application: Public load balancer -> private compute instances -> private database. Use OCI Flexible Load Balancer. Separate subnets for each tier.", "collection": "architecture_patterns", "source": "oracle/web-app-pattern"},
            {"id": "arch_003","content": "Microservices on OKE: OKE cluster with node pools, API Gateway for external access, Container Registry for images, OCI Streaming for async communication.", "collection": "architecture_patterns", "source": "oracle/oke-pattern"},
            {"id": "price_001","content": "OCI Compute: VM.Standard.E4.Flex $0.025/OCPU/hour + $0.0015/GB RAM/hour. VM.Standard.A1.Flex ARM $0.01/OCPU/hour. Always Free: 4 A1 OCPUs + 24GB RAM lifetime.", "collection": "pricing_info", "source": "oracle/compute-pricing"},
            {"id": "price_002","content": "OCI Storage: Object Storage $0.0255/GB/month standard, $0.0102 infrequent access, $0.0026 archive. Block Volume $0.0425/GB/month. File Storage $0.08/GB/month.", "collection": "pricing_info", "source": "oracle/storage-pricing"},
            {"id": "comp_001","content": "OCI compliance certifications: ISO 27001, SOC 1/2/3, PCI DSS Level 1, HIPAA, FedRAMP, GDPR. Built-in encryption at rest and in transit, comprehensive audit logging.", "collection": "compliance_standards", "source": "oracle/compliance-guide"},
        ]
        for doc in baseline_docs:
            self._document_store[doc["id"]] = {
                **doc,
                "indexed_at": datetime.utcnow().isoformat(),
                "word_count": len(doc["content"].split()),
            }
        logger.info("Seeded KB with %d baseline documents", len(baseline_docs))

    def add_document(self, content: str, collection: str, metadata: Optional[Dict] = None, source: str = "user-upload") -> str:
        """Add document to knowledge base."""
        if collection not in COLLECTIONS:
            raise ValueError(f"Unknown collection: {collection}")
        doc_id = hashlib.sha256(
            f"{collection}:{content[:100]}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]
        for i, chunk in enumerate(self._chunk_document(content)):
            chunk_id = f"{doc_id}_chunk_{i}"
            self._document_store[chunk_id] = {
                "id": chunk_id, "content": chunk, "collection": collection,
                "source": source, "metadata": metadata or {},
                "parent_doc_id": doc_id, "indexed_at": datetime.utcnow().isoformat(),
                "word_count": len(chunk.split()),
            }
        return doc_id

    def _chunk_document(self, content: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split document into overlapping chunks."""
        words = content.split()
        if len(words) <= chunk_size:
            return [content]
        chunks, start = [], 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunks.append(" ".join(words[start:end]))
            start += chunk_size - overlap
        return chunks

    def query(self, query_text: str, collection: str = "all", top_k: int = 5,
              migration_context: Optional[Dict] = None) -> Dict[str, Any]:
        """Query KB with keyword-based semantic search (vector search in production)."""
        query_words = set(query_text.lower().split())
        results = []
        for doc_id, doc in self._document_store.items():
            if collection != "all" and doc.get("collection") != collection:
                continue
            doc_words = set(doc["content"].lower().split())
            intersection = query_words & doc_words
            score = len(intersection) / (len(query_words) + 1)
            if migration_context and migration_context.get("source_provider", "").lower() in doc["content"].lower():
                score *= 1.2
            if score > 0:
                results.append({
                    "document_id": doc_id, "content": doc["content"],
                    "collection": doc.get("collection", "unknown"),
                    "source": doc.get("source", "unknown"),
                    "relevance_score": min(score * 5, 1.0),
                    "metadata": doc.get("metadata", {}),
                })
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        top_results = results[:top_k]
        if top_results:
            answer = f"Based on the Oracle Cloud migration knowledge base: {top_results[0]['content'][:400]}..."
        else:
            answer = f"No specific documentation found for '{query_text}'. Please consult Oracle documentation at docs.oracle.com."
        return {"query": query_text, "collection": collection, "answer": answer,
                "retrieved_documents": top_results, "total_results": len(results)}

    def search(self, query_text: str, collection: str = "all") -> List[Dict[str, Any]]:
        return self.query(query_text, collection)["retrieved_documents"]

    def query_service_mapping(self, source_service: str, source_provider: str = "AWS") -> Dict[str, Any]:
        results = self.query(f"{source_provider} {source_service} OCI equivalent", collection="service_mappings", top_k=3)
        return {"source_service": source_service, "source_provider": source_provider,
                "mapping_docs": results["retrieved_documents"], "answer": results["answer"]}

    def query_best_practices(self, topic: str) -> Dict[str, Any]:
        results = self.query(f"best practice {topic} migration OCI", collection="best_practices", top_k=3)
        return {"topic": topic, "practices": results["retrieved_documents"], "answer": results["answer"]}

    def query_architecture_patterns(self, pattern_type: str) -> Dict[str, Any]:
        results = self.query(f"{pattern_type} OCI architecture pattern", collection="architecture_patterns", top_k=3)
        return {"pattern_type": pattern_type, "patterns": results["retrieved_documents"], "answer": results["answer"]}

    def query_pricing_info(self, service_name: str, region: str = "us-ashburn-1") -> Dict[str, Any]:
        results = self.query(f"{service_name} OCI pricing cost", collection="pricing_info", top_k=3)
        return {"service": service_name, "region": region,
                "pricing_docs": results["retrieved_documents"], "answer": results["answer"]}

    def query_compliance_standards(self, standard: str) -> Dict[str, Any]:
        results = self.query(f"OCI {standard} compliance certification", collection="compliance_standards", top_k=3)
        return {"standard": standard, "compliance_docs": results["retrieved_documents"], "answer": results["answer"]}

    def list_collections(self) -> List[Dict[str, Any]]:
        stats: Dict[str, int] = {}
        for doc in self._document_store.values():
            coll = doc.get("collection", "unknown")
            stats[coll] = stats.get(coll, 0) + 1
        return [{"name": name, "description": info["description"], "document_count": stats.get(name, 0)}
                for name, info in COLLECTIONS.items()]

    def get_stats(self) -> Dict[str, Any]:
        return {"total_documents": len(self._document_store), "collections": self.list_collections(), "status": "operational"}


kb_manager = KnowledgeBaseManager()
