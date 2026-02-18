"""
Phase 2: Analysis - Agent nodes for OCI target architecture design.

This phase analyzes the discovered architecture and designs the target OCI solution.
"""

import time
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from src.models.state_schema import (
    MigrationState,
    PhaseStatus,
    OCIServiceMapping,
    ArchHubReference,
    LiveLabsWorkshop,
    SizingRecommendation,
    PricingEstimate
)
from src.utils.oci_genai import get_llm
from src.utils.logger import logger, log_node_entry, log_node_exit, log_mcp_call, log_llm_call, log_error

# MCP server singletons — direct in-process calls (no HTTP overhead)
from src.mcp_servers.mapping_server       import mapping_server
from src.mcp_servers.sizing_server        import sizing_server
from src.mcp_servers.pricing_server       import pricing_server
from src.mcp_servers.refarch_server       import refarch_server


# ── Phase 2 Node 1: Reconstruct Current State ────────────────────────────────

def reconstruct_current_state(state: MigrationState) -> MigrationState:
    """Build comprehensive model of current source architecture."""
    t0 = time.time()
    log_node_entry(state.migration_id, "analysis", "reconstruct_current_state", {
        "discovered_services": len(state.discovery.discovered_services),
        "compute_resources": len(state.discovery.compute_resources),
        "storage_resources": len(state.discovery.storage_resources),
        "source_provider": state.source_provider,
    })
    try:
        logger.info(f"Reconstructing current state for migration {state.migration_id}")

        state.current_phase = "analysis"
        state.phase_status = PhaseStatus.IN_PROGRESS

        llm = get_llm()

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a cloud architect reconstructing the current state
            of a cloud environment for migration planning.

            Based on the discovered services and architecture, create a comprehensive
            model that includes:
            1. Service inventory with dependencies
            2. Network topology
            3. Data flows
            4. Security boundaries
            5. Performance characteristics

            Focus on accuracy and completeness."""),
            ("user", "Discovery data: {discovery}")
        ])

        discovery_payload = str(state.discovery.dict())
        prompt_preview = f"[SYSTEM] Reconstruct current state. Discovery: {discovery_payload[:400]}"

        llm_t0 = time.time()
        chain = prompt | llm
        reconstruction = chain.invoke({"discovery": discovery_payload})
        llm_duration = (time.time() - llm_t0) * 1000

        log_llm_call(
            state.migration_id, "reconstruct_current_state",
            prompt_preview=prompt_preview,
            response_preview=str(reconstruction)[:800],
            duration_ms=llm_duration,
        )

        state.messages.append({
            "role": "system",
            "content": f"Current state reconstructed: {reconstruction}"
        })

        logger.info("Current state reconstruction complete")
        log_node_exit(state.migration_id, "analysis", "reconstruct_current_state", {
            "reconstruction_chars": len(str(reconstruction)),
        }, (time.time() - t0) * 1000)
        return state

    except Exception as e:
        log_error(state.migration_id, "ReconstructionError", str(e), "analysis")
        logger.error(f"Current state reconstruction failed: {str(e)}")
        state.errors.append(f"Reconstruction error: {str(e)}")
        return state


# ── Phase 2 Node 2: Service Mapping ─────────────────────────────────────────

def service_mapping(state: MigrationState) -> MigrationState:
    """
    Map source services to OCI equivalents.

    Strategy:
      1. Call mapping_server.bulk_map() for authoritative OCI service data.
      2. Use LLM only to enrich services that were not found in the mapping DB
         (confidence == 0) so the agent can still handle bespoke/unknown services.
    """
    t0 = time.time()
    service_names_input = [s.service_name for s in state.discovery.discovered_services]
    log_node_entry(state.migration_id, "analysis", "service_mapping", {
        "source_provider": state.source_provider,
        "service_count": len(service_names_input),
        "services": str(service_names_input[:20]),
    })
    try:
        logger.info(f"Mapping services to OCI for migration {state.migration_id}")

        provider = (state.source_provider or "AWS").strip()

        # ── Step 1: MCP server bulk lookup ────────────────────────────────────
        service_names = service_names_input or []
        if not service_names:
            service_names = ["EC2", "S3", "RDS", "VPC"]
            logger.warning("No discovered services; using default AWS service list")

        mcp_t0 = time.time()
        bulk_result = mapping_server.bulk_map(service_names, provider)
        mcp_duration = (time.time() - mcp_t0) * 1000

        log_mcp_call(
            state.migration_id, "mapping_server", "bulk_map",
            inputs={"services": service_names, "provider": provider},
            result={
                "total": bulk_result.get("total"),
                "auto_mapped": bulk_result.get("auto_mapped"),
                "avg_confidence": bulk_result.get("avg_confidence"),
                "sample_mappings": str([
                    f"{m.get('source_service')}→{m.get('oci_service')} ({m.get('confidence')})"
                    for m in bulk_result.get("mappings", [])[:5]
                ]),
            },
            duration_ms=mcp_duration,
        )

        mcp_mappings: List[OCIServiceMapping] = []
        unmapped_services: List[str] = []

        for item in bulk_result.get("mappings", []):
            conf = item.get("confidence", 0.0)
            svc_name = item.get("source_service", "")
            if conf > 0:
                mcp_mappings.append(OCIServiceMapping(
                    source_service=svc_name,
                    oci_service=item.get("oci_service", ""),
                    mapping_confidence=conf,
                    alternatives=[item.get("oci_resource", "")] if item.get("oci_resource") else [],
                    reasoning=(
                        f"{item.get('notes', '')} "
                        f"[Effort: {item.get('migration_effort', 'unknown')}. "
                        f"Docs: {item.get('oci_doc_url', '')}]"
                    ).strip(),
                ))
            else:
                unmapped_services.append(svc_name)

        logger.info(
            f"MCP mapping: {len(mcp_mappings)} mapped, "
            f"{len(unmapped_services)} need LLM enrichment"
        )

        # ── Step 2: LLM enrichment for unknown services ───────────────────────
        llm_mappings: List[OCIServiceMapping] = []
        if unmapped_services:
            llm = get_llm()
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an OCI migration expert. For each unknown source
                service below, produce a JSON array where every element has:
                  source_service, oci_service, mapping_confidence (0-1),
                  alternatives (list of strings), reasoning (string).
                Use your knowledge of OCI services. Return only valid JSON."""),
                ("user", "Provider: {provider}\nUnknown services: {services}"),
            ])
            prompt_preview = (
                f"[SYSTEM] Map unknown services. "
                f"Provider: {provider}. Services: {unmapped_services}"
            )
            llm_t0 = time.time()
            chain = prompt | llm | JsonOutputParser()
            try:
                llm_data = chain.invoke({
                    "provider": provider,
                    "services": unmapped_services,
                })
                llm_duration = (time.time() - llm_t0) * 1000
                log_llm_call(
                    state.migration_id, "service_mapping_llm_enrichment",
                    prompt_preview=prompt_preview,
                    response_preview=str(llm_data)[:500],
                    duration_ms=llm_duration,
                )
                for m in (llm_data if isinstance(llm_data, list) else []):
                    llm_mappings.append(OCIServiceMapping(**m))
            except Exception as llm_err:
                logger.warning(f"LLM enrichment failed for unmapped services: {llm_err}")

        state.analysis.service_mappings = mcp_mappings + llm_mappings
        logger.info(
            f"Total service mappings: {len(state.analysis.service_mappings)} "
            f"({len(mcp_mappings)} MCP, {len(llm_mappings)} LLM)"
        )
        log_node_exit(state.migration_id, "analysis", "service_mapping", {
            "total_mappings": len(state.analysis.service_mappings),
            "mcp_count": len(mcp_mappings),
            "llm_count": len(llm_mappings),
            "unmapped": len(unmapped_services),
            "oci_services": str([m.oci_service for m in state.analysis.service_mappings[:10]]),
        }, (time.time() - t0) * 1000)
        return state

    except Exception as e:
        log_error(state.migration_id, "ServiceMappingError", str(e), "analysis")
        logger.error(f"Service mapping failed: {str(e)}")
        state.errors.append(f"Service mapping error: {str(e)}")
        return state


# ── Phase 2 Node 3: ArchHub Discovery ────────────────────────────────────────

# LiveLabs workshops are curated by topic; we map from identified OCI services.
_LIVELABS_CATALOGUE = [
    {"workshop_id": "ll-oci-compute-migration",    "title": "Migrate Virtual Machines to OCI Compute",           "url": "https://apexapps.oracle.com/pls/apex/f?p=133:100:::::P100_SEARCH:compute+migration",       "topics": ["Compute", "Migration", "Networking"],                  "keywords": ["compute", "ec2", "vm", "virtual machine"]},
    {"workshop_id": "ll-oci-adb-migration",         "title": "Migrate Databases to Autonomous Database (ATP/ADW)", "url": "https://apexapps.oracle.com/pls/apex/f?p=133:100:::::P100_SEARCH:autonomous+database",      "topics": ["Database", "Autonomous", "Migration"],                 "keywords": ["database", "rds", "oracle", "mysql", "postgresql", "autonomous"]},
    {"workshop_id": "ll-oci-oke-microservices",     "title": "Deploy Microservices on OKE",                        "url": "https://apexapps.oracle.com/pls/apex/f?p=133:100:::::P100_SEARCH:oke+microservices",         "topics": ["OKE", "Kubernetes", "Containers", "Microservices"],    "keywords": ["kubernetes", "oke", "eks", "aks", "gke", "containers", "docker"]},
    {"workshop_id": "ll-oci-object-storage",        "title": "OCI Object Storage — S3 Migration",                  "url": "https://apexapps.oracle.com/pls/apex/f?p=133:100:::::P100_SEARCH:object+storage",           "topics": ["Object Storage", "Migration", "S3"],                   "keywords": ["s3", "blob", "object storage", "gcs"]},
    {"workshop_id": "ll-oci-networking",            "title": "OCI Networking Fundamentals & VCN Design",           "url": "https://apexapps.oracle.com/pls/apex/f?p=133:100:::::P100_SEARCH:vcn+networking",            "topics": ["VCN", "Networking", "Subnets", "Security"],            "keywords": ["vpc", "vcn", "networking", "subnet", "security group"]},
    {"workshop_id": "ll-oci-devops",                "title": "OCI DevOps: CI/CD Pipelines",                        "url": "https://apexapps.oracle.com/pls/apex/f?p=133:100:::::P100_SEARCH:devops",                    "topics": ["DevOps", "CI/CD", "Container Registry"],              "keywords": ["devops", "ci/cd", "pipeline", "codebuild", "codedeploy", "azure devops"]},
    {"workshop_id": "ll-oci-terraform",             "title": "Infrastructure as Code with OCI Terraform",          "url": "https://apexapps.oracle.com/pls/apex/f?p=133:100:::::P100_SEARCH:terraform",                  "topics": ["Terraform", "IaC", "Resource Manager"],               "keywords": ["terraform", "cloudformation", "iac", "resource manager"]},
    {"workshop_id": "ll-oci-security",              "title": "OCI Security: Vault, WAF, Cloud Guard",              "url": "https://apexapps.oracle.com/pls/apex/f?p=133:100:::::P100_SEARCH:security",                   "topics": ["Security", "Vault", "Cloud Guard", "WAF"],             "keywords": ["security", "vault", "kms", "waf", "cloud guard", "compliance"]},
    {"workshop_id": "ll-oci-analytics",             "title": "Oracle Analytics Cloud & ADW",                       "url": "https://apexapps.oracle.com/pls/apex/f?p=133:100:::::P100_SEARCH:analytics",                  "topics": ["Analytics", "ADW", "OAC", "Data Warehouse"],          "keywords": ["analytics", "redshift", "bigquery", "synapse", "data warehouse", "bi"]},
    {"workshop_id": "ll-oci-functions",             "title": "Serverless Functions on OCI",                        "url": "https://apexapps.oracle.com/pls/apex/f?p=133:100:::::P100_SEARCH:functions",                  "topics": ["Functions", "Serverless", "API Gateway"],             "keywords": ["lambda", "functions", "serverless", "api gateway"]},
    {"workshop_id": "ll-oci-mysql-heatwave",        "title": "MySQL HeatWave — Migration & Analytics",             "url": "https://apexapps.oracle.com/pls/apex/f?p=133:100:::::P100_SEARCH:mysql+heatwave",             "topics": ["MySQL", "HeatWave", "Database", "Analytics"],         "keywords": ["mysql", "aurora", "heatwave"]},
    {"workshop_id": "ll-oci-dr",                    "title": "OCI Full Stack Disaster Recovery",                   "url": "https://apexapps.oracle.com/pls/apex/f?p=133:100:::::P100_SEARCH:disaster+recovery",          "topics": ["Disaster Recovery", "HA", "Full Stack DR"],           "keywords": ["disaster recovery", "dr", "failover", "ha", "high availability"]},
]


def archhub_discovery(state: MigrationState) -> MigrationState:
    """
    Discover relevant OCI Architecture Center reference architectures
    by calling the RefArch MCP server with the actual services and context.
    """
    t0 = time.time()
    services = [m.oci_service for m in state.analysis.service_mappings] if state.analysis.service_mappings else []
    description = (
        f"{state.user_context} "
        f"Source provider: {state.source_provider}. "
        f"Services: {', '.join(services[:10])}."
    )
    log_node_entry(state.migration_id, "analysis", "archhub_discovery", {
        "services_count": len(services),
        "oci_services": str(services[:10]),
        "description_preview": description[:200],
    })
    try:
        logger.info(f"Discovering ArchHub references for migration {state.migration_id}")

        mcp_t0 = time.time()
        result = refarch_server.match_pattern(
            architecture_description=description,
            services=services,
            source_provider=state.source_provider,
        )
        mcp_duration = (time.time() - mcp_t0) * 1000

        best = result.get("best_match", {})
        log_mcp_call(
            state.migration_id, "refarch_server", "match_pattern",
            inputs={
                "architecture_description": description[:300],
                "services": services[:10],
                "source_provider": state.source_provider,
            },
            result={
                "best_match_name": best.get("name", "none"),
                "best_match_score": best.get("match_score", 0),
                "alternatives_count": len(result.get("alternatives", [])),
                "best_components": str(best.get("components", [])[:3]),
            },
            duration_ms=mcp_duration,
        )

        references: List[ArchHubReference] = []

        if best:
            references.append(ArchHubReference(
                architecture_id=best.get("template_id", "arch-001"),
                title=best.get("name", "OCI Reference Architecture"),
                description=best.get("description", "")[:200],
                diagram_url=best.get("architecture_url", "https://docs.oracle.com/en/solutions/"),
                components=best.get("components", []),
                match_score=best.get("match_score", 0.85),
            ))

        for i, alt in enumerate(result.get("alternatives", [])[:2]):
            references.append(ArchHubReference(
                architecture_id=alt.get("template_id", f"arch-00{i+2}"),
                title=alt.get("name", "Alternative Architecture"),
                description=alt.get("description", "")[:200],
                diagram_url=alt.get("architecture_url", "https://docs.oracle.com/en/solutions/"),
                components=alt.get("oci_services", []),
                match_score=alt.get("match_score", 0.60),
            ))

        state.analysis.archhub_references = references
        logger.info(f"Found {len(references)} ArchHub references via RefArch MCP server")
        log_node_exit(state.migration_id, "analysis", "archhub_discovery", {
            "references_count": len(references),
            "best_match": best.get("name", "none"),
            "best_score": best.get("match_score", 0),
        }, (time.time() - t0) * 1000)
        return state

    except Exception as e:
        log_error(state.migration_id, "ArchHubError", str(e), "analysis")
        logger.error(f"ArchHub discovery failed: {str(e)}")
        state.errors.append(f"ArchHub error: {str(e)}")
        return state


# ── Phase 2 Node 4: LiveLabs Discovery ───────────────────────────────────────

def livelabs_discovery(state: MigrationState) -> MigrationState:
    """
    Select relevant OCI LiveLabs workshops based on the mapped services
    and user context, without requiring an external API call.
    """
    t0 = time.time()
    log_node_entry(state.migration_id, "analysis", "livelabs_discovery", {
        "service_mappings_count": len(state.analysis.service_mappings),
        "user_context_preview": state.user_context[:200] if state.user_context else "",
    })
    try:
        logger.info(f"Discovering LiveLabs workshops for migration {state.migration_id}")

        context_lower = state.user_context.lower()
        service_keywords = set()
        for m in state.analysis.service_mappings:
            service_keywords.add(m.source_service.lower())
            service_keywords.add(m.oci_service.lower())
        for svc in state.discovery.discovered_services:
            service_keywords.add(svc.service_name.lower())

        logger.info(
            f"LiveLabs keyword set ({len(service_keywords)} terms): "
            f"{str(list(service_keywords)[:15])}"
        )

        scored = []
        for ws in _LIVELABS_CATALOGUE:
            score = 0.0
            for kw in ws["keywords"]:
                if kw in context_lower or any(kw in sk for sk in service_keywords):
                    score += 0.20
            scored.append((score, ws))

        scored.sort(key=lambda x: x[0], reverse=True)

        workshops: List[LiveLabsWorkshop] = []
        for score, ws in scored[:4]:
            if score > 0 or len(workshops) < 2:
                workshops.append(LiveLabsWorkshop(
                    workshop_id=ws["workshop_id"],
                    title=ws["title"],
                    description=f"OCI LiveLabs: {ws['title']}",
                    url=ws["url"],
                    relevance_score=min(round(score, 2) if score > 0 else 0.50, 1.0),
                    topics=ws["topics"],
                ))

        ws_ids = {w.workshop_id for w in workshops}
        for ws in _LIVELABS_CATALOGUE:
            if ws["workshop_id"] in ("ll-oci-networking", "ll-oci-terraform") and ws["workshop_id"] not in ws_ids:
                workshops.append(LiveLabsWorkshop(
                    workshop_id=ws["workshop_id"],
                    title=ws["title"],
                    description=f"OCI LiveLabs: {ws['title']}",
                    url=ws["url"],
                    relevance_score=0.70,
                    topics=ws["topics"],
                ))

        state.analysis.livelabs_workshops = workshops
        logger.info(f"Selected {len(workshops)} LiveLabs workshops based on context")
        log_node_exit(state.migration_id, "analysis", "livelabs_discovery", {
            "workshops_count": len(workshops),
            "workshop_titles": str([w.title for w in workshops]),
        }, (time.time() - t0) * 1000)
        return state

    except Exception as e:
        log_error(state.migration_id, "LiveLabsError", str(e), "analysis")
        logger.error(f"LiveLabs discovery failed: {str(e)}")
        state.errors.append(f"LiveLabs error: {str(e)}")
        return state


# ── Phase 2 Node 5: Target Design ────────────────────────────────────────────

def target_design(state: MigrationState) -> MigrationState:
    """Design target OCI architecture."""
    t0 = time.time()
    log_node_entry(state.migration_id, "analysis", "target_design", {
        "service_mappings": len(state.analysis.service_mappings),
        "archhub_references": len(state.analysis.archhub_references),
        "livelabs_workshops": len(state.analysis.livelabs_workshops),
    })
    try:
        logger.info(f"Designing target OCI architecture for migration {state.migration_id}")

        llm = get_llm()

        mappings_payload = str([m.dict() for m in state.analysis.service_mappings])
        archhub_payload  = str([a.dict() for a in state.analysis.archhub_references])
        livelabs_payload = str([l.dict() for l in state.analysis.livelabs_workshops])

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an OCI solutions architect designing a target architecture.

            Based on:
            - Service mappings
            - ArchHub reference architectures
            - LiveLabs best practices

            Create a comprehensive OCI target design that includes:
            1. Network architecture (VCN, subnets, gateways)
            2. Compute resources (shapes, configurations)
            3. Storage layout (Object Storage, Block Volumes, File Storage)
            4. Database configuration
            5. Security design (IAM, security lists, NSGs)
            6. High availability and disaster recovery

            Follow OCI best practices and Well-Architected Framework principles."""),
            ("user", """Service mappings: {mappings}
            ArchHub refs: {archhub}
            LiveLabs: {livelabs}""")
        ])

        prompt_preview = (
            f"[SYSTEM] Design OCI target architecture. "
            f"Mappings ({len(state.analysis.service_mappings)}): {mappings_payload[:300]} "
            f"ArchHub: {archhub_payload[:200]}"
        )

        llm_t0 = time.time()
        chain = prompt | llm
        target_design_result = chain.invoke({
            "mappings": mappings_payload,
            "archhub":  archhub_payload,
            "livelabs": livelabs_payload,
        })
        llm_duration = (time.time() - llm_t0) * 1000

        log_llm_call(
            state.migration_id, "target_design",
            prompt_preview=prompt_preview,
            response_preview=str(target_design_result)[:800],
            duration_ms=llm_duration,
        )

        state.messages.append({
            "role": "system",
            "content": f"Target OCI design: {target_design_result}"
        })

        logger.info("Target OCI architecture design complete")
        log_node_exit(state.migration_id, "analysis", "target_design", {
            "design_chars": len(str(target_design_result)),
        }, (time.time() - t0) * 1000)
        return state

    except Exception as e:
        log_error(state.migration_id, "TargetDesignError", str(e), "analysis")
        logger.error(f"Target design failed: {str(e)}")
        state.errors.append(f"Target design error: {str(e)}")
        return state


# ── Phase 2 Node 6: Resource Sizing ──────────────────────────────────────────

def resource_sizing(state: MigrationState) -> MigrationState:
    """
    Size OCI resources by calling the Sizing MCP server for each
    source compute/storage resource discovered in Phase 1.
    """
    t0 = time.time()
    log_node_entry(state.migration_id, "analysis", "resource_sizing", {
        "compute_resources": len(state.discovery.compute_resources),
        "storage_resources": len(state.discovery.storage_resources),
        "source_provider": state.source_provider,
    })
    try:
        logger.info(f"Sizing OCI resources for migration {state.migration_id}")

        recommendations: List[SizingRecommendation] = []
        provider = state.source_provider or "AWS"

        # ── Compute instances ─────────────────────────────────────────────────
        for compute in state.discovery.compute_resources:
            instance_type = compute.instance_type or "m5.xlarge"
            mcp_t0 = time.time()
            result = sizing_server.estimate_compute(
                source_instance_type=instance_type,
                source_provider=provider,
                workload_type="general",
            )
            mcp_duration = (time.time() - mcp_t0) * 1000
            log_mcp_call(
                state.migration_id, "sizing_server", "estimate_compute",
                inputs={"source_instance_type": instance_type, "source_provider": provider, "workload_type": "general"},
                result={
                    "recommended_shape": result.get("recommended_shape"),
                    "ocpu": result.get("ocpu"),
                    "memory_gb": result.get("memory_gb"),
                    "oci_monthly_cost_usd": result.get("oci_monthly_cost_usd"),
                    "source_monthly_cost_usd": result.get("source_monthly_cost_usd"),
                    "estimated_savings_pct": result.get("estimated_savings_pct"),
                    "confidence": result.get("confidence"),
                },
                duration_ms=mcp_duration,
            )
            recommendations.append(SizingRecommendation(
                resource_type="Compute",
                recommended_shape=result.get("recommended_shape", "VM.Standard.E4.Flex"),
                vcpus=result.get("ocpu", 2),
                memory_gb=result.get("memory_gb", 16),
                storage_gb=compute.storage_gb or 100,
                rationale=(
                    f"Mapped from {provider} {instance_type} → {result.get('recommended_shape')}. "
                    f"Est. OCI cost: ${result.get('oci_monthly_cost_usd', 0):.2f}/mo. "
                    f"Confidence: {result.get('confidence', 0.9):.0%}."
                ),
            ))

        # ── Storage resources ─────────────────────────────────────────────────
        for storage in state.discovery.storage_resources:
            stype = storage.storage_type or "block"
            size  = storage.size_gb or 100
            mcp_t0 = time.time()
            s_result = sizing_server.estimate_storage(
                storage_type=stype,
                size_gb=size,
                iops=storage.iops,
            )
            mcp_duration = (time.time() - mcp_t0) * 1000
            log_mcp_call(
                state.migration_id, "sizing_server", "estimate_storage",
                inputs={"storage_type": stype, "size_gb": size, "iops": storage.iops},
                result={
                    "oci_service": s_result.get("oci_service"),
                    "monthly_cost_usd": s_result.get("monthly_cost_usd"),
                    "recommended_vpu": s_result.get("recommended_vpu"),
                },
                duration_ms=mcp_duration,
            )
            recommendations.append(SizingRecommendation(
                resource_type="Storage",
                recommended_shape=s_result.get("oci_service", "Block Volume"),
                vcpus=0,
                memory_gb=0,
                storage_gb=size,
                rationale=(
                    f"Mapped {provider} {stype} ({size} GB) → {s_result.get('oci_service')}. "
                    f"Est. cost: ${s_result.get('monthly_cost_usd', 0):.2f}/mo."
                ),
            ))

        # ── Fallback defaults if discovery found nothing ──────────────────────
        if not recommendations:
            logger.warning("No compute/storage resources discovered; using default sizing")
            mcp_t0 = time.time()
            compute_result = sizing_server.estimate_compute("m5.xlarge", provider, "general")
            mcp_duration = (time.time() - mcp_t0) * 1000
            log_mcp_call(
                state.migration_id, "sizing_server", "estimate_compute (default)",
                inputs={"source_instance_type": "m5.xlarge", "source_provider": provider},
                result={
                    "recommended_shape": compute_result.get("recommended_shape"),
                    "oci_monthly_cost_usd": compute_result.get("oci_monthly_cost_usd"),
                },
                duration_ms=mcp_duration,
            )
            recommendations = [
                SizingRecommendation(
                    resource_type="Compute",
                    recommended_shape=compute_result.get("recommended_shape", "VM.Standard.E4.Flex"),
                    vcpus=compute_result.get("ocpu", 2),
                    memory_gb=compute_result.get("memory_gb", 16),
                    storage_gb=100,
                    rationale=(
                        f"Default sizing based on medium workload estimate. "
                        f"Shape: {compute_result.get('recommended_shape')}. "
                        f"Cost: ${compute_result.get('oci_monthly_cost_usd', 0):.2f}/mo."
                    ),
                ),
                SizingRecommendation(
                    resource_type="Database",
                    recommended_shape="Autonomous Database OLTP",
                    vcpus=2,
                    memory_gb=16,
                    storage_gb=1024,
                    rationale=(
                        "Autonomous Database recommended for reduced management overhead, "
                        "auto-scaling, and built-in security."
                    ),
                ),
            ]

        state.analysis.sizing_recommendations = recommendations
        logger.info(f"Created {len(recommendations)} sizing recommendations via Sizing MCP server")
        log_node_exit(state.migration_id, "analysis", "resource_sizing", {
            "recommendations_count": len(recommendations),
            "shapes": str([r.recommended_shape for r in recommendations]),
        }, (time.time() - t0) * 1000)
        return state

    except Exception as e:
        log_error(state.migration_id, "ResourceSizingError", str(e), "analysis")
        logger.error(f"Resource sizing failed: {str(e)}")
        state.errors.append(f"Resource sizing error: {str(e)}")
        return state


# ── Phase 2 Node 7: Cost Estimation ──────────────────────────────────────────

def cost_estimation(state: MigrationState) -> MigrationState:
    """
    Estimate OCI costs by calling the Pricing MCP server based on
    the sizing recommendations produced in Node 6.
    """
    t0 = time.time()
    log_node_entry(state.migration_id, "analysis", "cost_estimation", {
        "sizing_recommendations": len(state.analysis.sizing_recommendations),
        "shapes": str([r.recommended_shape for r in state.analysis.sizing_recommendations]),
    })
    try:
        logger.info(f"Estimating OCI costs for migration {state.migration_id}")

        # Build resource list from sizing recommendations
        resources = []
        for rec in state.analysis.sizing_recommendations:
            rtype = rec.resource_type.lower()
            if rtype == "compute":
                resources.append({
                    "type": "compute",
                    "name": f"Compute — {rec.recommended_shape}",
                    "shape": rec.recommended_shape,
                    "ocpu": rec.vcpus,
                    "memory_gb": rec.memory_gb,
                    "quantity": 1,
                })
            elif rtype == "storage":
                storage_class_map = {
                    "Object Storage": "Object Storage Standard",
                    "Block Volume":   "Block Volume",
                    "File Storage":   "File Storage",
                    "Archive Storage":"Archive Storage",
                }
                cls = storage_class_map.get(rec.recommended_shape, "Block Volume")
                resources.append({
                    "type": "storage",
                    "name": f"Storage — {rec.recommended_shape}",
                    "storage_class": cls,
                    "size_gb": rec.storage_gb or 100,
                    "quantity": 1,
                })
            elif rtype == "database":
                db_map = {
                    "Autonomous Database OLTP": "Autonomous Database OLTP",
                    "Autonomous Database":      "Autonomous Database OLTP",
                    "MySQL HeatWave":           "MySQL HeatWave",
                    "Oracle Database SE2":      "Oracle Database SE2",
                    "Oracle Database EE":       "Oracle Database EE",
                }
                db_svc = db_map.get(rec.recommended_shape, "Autonomous Database OLTP")
                resources.append({
                    "type": "database",
                    "name": f"Database — {rec.recommended_shape}",
                    "db_service": db_svc,
                    "ocpu": rec.vcpus or 2,
                    "storage_tb": round((rec.storage_gb or 1024) / 1024, 2),
                    "quantity": 1,
                })

        if not resources:
            resources = [
                {"type": "compute",  "name": "App Compute",   "shape": "VM.Standard.E4.Flex", "ocpu": 2,  "memory_gb": 16, "quantity": 2},
                {"type": "database", "name": "Autonomous DB",  "db_service": "Autonomous Database OLTP", "ocpu": 2, "storage_tb": 1},
                {"type": "storage",  "name": "Object Storage", "storage_class": "Object Storage Standard", "size_gb": 500},
                {"type": "load_balancer", "name": "Load Balancer", "lb_type": "flexible", "quantity": 1},
            ]

        resources.extend([
            {"type": "load_balancer", "name": "Load Balancer (Flexible)", "lb_type": "flexible", "quantity": 1},
            {"type": "nat_gateway",   "name": "NAT Gateway",              "quantity": 1},
        ])

        logger.info(
            f"Calling pricing_server.oci_estimate with {len(resources)} resources: "
            f"{str([r.get('name', r.get('type')) for r in resources])}"
        )

        mcp_t0 = time.time()
        result = pricing_server.oci_estimate(resources)
        mcp_duration = (time.time() - mcp_t0) * 1000

        log_mcp_call(
            state.migration_id, "pricing_server", "oci_estimate",
            inputs={"resources_count": len(resources), "resource_names": str([r.get("name") for r in resources])},
            result={
                "total_monthly_cost_usd": result.get("total_monthly_cost_usd"),
                "total_annual_cost_usd": result.get("total_annual_cost_usd"),
                "line_items_count": len(result.get("line_items", [])),
                "line_items_preview": str([
                    f"{li.get('name')}: ${li.get('monthly_cost_usd', 0):.2f}"
                    for li in result.get("line_items", [])
                ]),
            },
            duration_ms=mcp_duration,
        )

        pricing_estimates: List[PricingEstimate] = []
        for item in result.get("line_items", []):
            monthly = item.get("monthly_cost_usd", 0.0)
            pricing_estimates.append(PricingEstimate(
                resource_name=item.get("name", item.get("type", "resource")),
                monthly_cost_usd=monthly,
                annual_cost_usd=round(monthly * 12, 2),
                cost_breakdown=item.get("detail", {}),
            ))

        state.analysis.pricing_estimates = pricing_estimates
        state.analysis.total_monthly_cost_usd = result.get("total_monthly_cost_usd", 0.0)
        state.analysis.total_annual_cost_usd  = result.get("total_annual_cost_usd",  0.0)

        if state.analysis.total_monthly_cost_usd > 0:
            mcp_t0 = time.time()
            savings = pricing_server.compare_with_source(
                source_monthly_cost=state.analysis.total_monthly_cost_usd * 1.4,
                oci_monthly_cost=state.analysis.total_monthly_cost_usd,
            )
            mcp_duration = (time.time() - mcp_t0) * 1000
            log_mcp_call(
                state.migration_id, "pricing_server", "compare_with_source",
                inputs={
                    "source_monthly_cost": round(state.analysis.total_monthly_cost_usd * 1.4, 2),
                    "oci_monthly_cost": round(state.analysis.total_monthly_cost_usd, 2),
                },
                result=savings,
                duration_ms=mcp_duration,
            )
            state.analysis.savings_analysis = savings

        logger.info(
            f"Cost estimation complete via Pricing MCP server: "
            f"${state.analysis.total_monthly_cost_usd:.2f}/month, "
            f"${state.analysis.total_annual_cost_usd:.2f}/year"
        )
        log_node_exit(state.migration_id, "analysis", "cost_estimation", {
            "total_monthly_cost_usd": round(state.analysis.total_monthly_cost_usd, 2),
            "total_annual_cost_usd": round(state.analysis.total_annual_cost_usd, 2),
            "pricing_estimates_count": len(pricing_estimates),
            "savings_pct": state.analysis.savings_analysis.get("savings_percentage", 0),
        }, (time.time() - t0) * 1000)
        return state

    except Exception as e:
        log_error(state.migration_id, "CostEstimationError", str(e), "analysis")
        logger.error(f"Cost estimation failed: {str(e)}")
        state.errors.append(f"Cost estimation error: {str(e)}")
        return state
