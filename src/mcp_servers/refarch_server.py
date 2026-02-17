"""MCP Server 5: Reference Architectures (refarch)."""
import time
from typing import Any, Dict, List, Optional

TEMPLATES = [
    {"template_id": "landing-zone-v2",    "name": "OCI Landing Zone",             "description": "Secure OCI foundation",                       "category": "Foundation",      "components": ["VCN", "IAM", "Security Lists", "Bastion"],                "complexity": "medium"},
    {"template_id": "three-tier-web-app", "name": "Three-Tier Web Application",   "description": "Load-balanced web app with private database",  "category": "Web Application", "components": ["Load Balancer", "Compute", "Database", "VCN"],             "complexity": "low"},
    {"template_id": "microservices-oke",  "name": "Microservices on OKE",         "description": "Kubernetes microservices",                     "category": "Kubernetes",      "components": ["OKE", "API Gateway", "Container Registry", "VCN"],           "complexity": "high"},
    {"template_id": "data-platform",      "name": "OCI Data Platform",            "description": "Data warehouse and analytics",                 "category": "Data & Analytics","components": ["ADW", "Data Integration", "OAC", "Object Storage"],          "complexity": "medium"},
]


class RefArchServer:
    SERVER_NAME = "refarch"
    VERSION = "1.0.0"

    def __init__(self):
        self._call_count = 0
        self._success_count = 0
        self._total_latency_ms = 0

    def _record_call(self, latency_ms: float, success: bool = True):
        self._call_count += 1
        if success: self._success_count += 1
        self._total_latency_ms += latency_ms

    def list_templates(self, category=None) -> Dict[str, Any]:
        start = time.time()
        templates = TEMPLATES if not category else [t for t in TEMPLATES if t["category"].lower() == category.lower()]
        self._record_call((time.time() - start) * 1000)
        return {"templates": templates, "total": len(templates)}

    def get_template(self, template_id: str) -> Dict[str, Any]:
        start = time.time()
        template = next((t for t in TEMPLATES if t["template_id"] == template_id), None)
        self._record_call((time.time() - start) * 1000)
        return {"template": template, "found": template is not None}

    def match_pattern(self, architecture_description: str, services: List[str]) -> Dict[str, Any]:
        start = time.time()
        scored = []
        for t in TEMPLATES:
            score = sum(0.2 for s in services if any(s.lower() in c.lower() for c in t["components"]))
            scored.append({"template": t, "match_score": min(score, 1.0)})
        scored.sort(key=lambda x: x["match_score"], reverse=True)
        self._record_call((time.time() - start) * 1000)
        return {"best_match": scored[0] if scored else None, "alternatives": scored[1:3]}

    def get_health_metrics(self) -> Dict[str, Any]:
        return {"server": self.SERVER_NAME, "total_calls": self._call_count, "success_rate": self._success_count / max(self._call_count, 1), "avg_latency_ms": 0, "status": "healthy"}


refarch_server = RefArchServer()
