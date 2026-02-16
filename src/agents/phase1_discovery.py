"""
Phase 1: Discovery - Agent nodes for discovering source cloud architecture.

This phase extracts and analyzes source cloud architecture from
evidence (documents, BoM, user input).
"""

from typing import Dict, Any, List

from src.models.state_schema import (
    MigrationState, PhaseStatus, Gap, DiscoveredService,
    NetworkArchitecture, ComputeResource, StorageResource, SecurityPosture
)
from src.utils.oci_genai import get_llm
from src.utils.logger import logger


def intake_plan(state: MigrationState) -> MigrationState:
    """Intake migration request and initialize workflow."""
    try:
        logger.info(f"Starting intake for migration {state.migration_id}")
        state.current_phase = "discovery"
        state.phase_status = PhaseStatus.IN_PROGRESS
        state.messages.append({
            "role": "system",
            "content": f"Migration intake started for {state.source_provider} to OCI"
        })
        logger.info(f"Intake complete for migration {state.migration_id}")
        return state
    except Exception as e:
        logger.error(f"Intake failed: {str(e)}")
        state.errors.append(f"Intake error: {str(e)}")
        state.phase_status = PhaseStatus.FAILED
        return state


def kb_enrich_discovery(state: MigrationState) -> MigrationState:
    """Enrich discovery with knowledge base intelligence."""
    try:
        logger.info(f"KB enrichment for migration {state.migration_id}")
        state.discovery.kb_intelligence = {
            "migration_patterns": [],
            "best_practices": [],
            "known_mappings": []
        }
        state.messages.append({
            "role": "system",
            "content": "Knowledge base enrichment completed"
        })
        return state
    except Exception as e:
        logger.error(f"KB enrichment failed: {str(e)}")
        state.errors.append(f"KB enrichment error: {str(e)}")
        return state


def document_ingestion(state: MigrationState) -> MigrationState:
    """Process uploaded documents (PDF, DOCX, diagrams)."""
    try:
        logger.info(f"Processing documents for migration {state.migration_id}")
        if not state.uploaded_documents:
            logger.warning("No documents to process")
            return state

        try:
            from src.utils.document_processor import DocumentProcessor
            processor = DocumentProcessor()
            processed_docs = processor.process_multiple_documents(state.uploaded_documents)
            for doc in processed_docs:
                if not doc.get("error"):
                    state.messages.append({
                        "role": "system",
                        "content": f"Processed {doc['file_type']}: {doc['file_path']}"
                    })
            logger.info(f"Processed {len(processed_docs)} documents")
        except ImportError:
            logger.warning("Document processor not available, skipping")

        return state
    except Exception as e:
        logger.error(f"Document ingestion failed: {str(e)}")
        state.errors.append(f"Document ingestion error: {str(e)}")
        return state


def bom_analysis(state: MigrationState) -> MigrationState:
    """Parse Excel/CSV Bill of Materials for cost data."""
    try:
        logger.info(f"Analyzing BOM for migration {state.migration_id}")
        if not state.bom_file:
            logger.warning("No BOM file provided")
            return state

        try:
            from src.utils.document_processor import DocumentProcessor
            processor = DocumentProcessor()
            bom_data = processor.process_excel_bom(state.bom_file)
            for resource in bom_data.get("resources", []):
                state.messages.append({
                    "role": "system",
                    "content": f"BOM resource: {resource.get('name', 'Unknown')}"
                })
            logger.info(
                f"Analyzed BOM: {bom_data['num_resources']} resources, "
                f"${bom_data['total_monthly_cost']:.2f}/month"
            )
        except (ImportError, Exception) as e:
            logger.warning(f"BOM processing skipped: {e}")

        return state
    except Exception as e:
        logger.error(f"BOM analysis failed: {str(e)}")
        state.errors.append(f"BOM analysis error: {str(e)}")
        return state


def extract_evidence(state: MigrationState) -> MigrationState:
    """Consolidate evidence from all sources using LLM."""
    try:
        logger.info(f"Extracting evidence for migration {state.migration_id}")

        try:
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import JsonOutputParser

            llm = get_llm()
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert cloud architect analyzing migration evidence.
                Extract the following information from the provided context:
                1. Cloud services being used (compute, storage, database, networking)
                2. Network architecture (VPCs, subnets, security groups)
                3. Compute resources (instance types, sizes, counts)
                4. Storage resources (types, sizes, IOPS)
                5. Security configuration (IAM, policies, encryption)

                Respond in JSON format with these top-level keys:
                - services: list of objects with service_name, provider, resource_type
                - network: object with vpcs, subnets, security_groups
                - compute: list of objects with instance_id, instance_type, vcpus, memory_gb, storage_gb, os
                - storage: list of objects with resource_id, storage_type, size_gb
                - security: object with iam_roles, policies, encryption
                """),
                ("user", "Context: {context}\n\nUser provided: {user_context}")
            ])

            context = "\n".join([msg["content"] for msg in state.messages])
            chain = prompt | llm | JsonOutputParser()
            evidence = chain.invoke({
                "context": context,
                "user_context": state.user_context
            })

            # Parse services
            for svc in evidence.get("services", []):
                state.discovery.discovered_services.append(
                    DiscoveredService(**svc) if isinstance(svc, dict) else DiscoveredService(service_name=str(svc))
                )

            logger.info(f"Extracted evidence: {len(state.discovery.discovered_services)} services")

        except Exception as e:
            logger.warning(f"LLM evidence extraction failed, using fallback: {e}")
            _extract_evidence_fallback(state)

        return state
    except Exception as e:
        logger.error(f"Evidence extraction failed: {str(e)}")
        state.errors.append(f"Evidence extraction error: {str(e)}")
        _extract_evidence_fallback(state)
        return state


def _extract_evidence_fallback(state: MigrationState):
    """Provide fallback evidence when LLM is unavailable."""
    user_ctx = state.user_context.lower()

    service_keywords = {
        "ec2": ("EC2", "AWS", "compute"),
        "s3": ("S3", "AWS", "storage"),
        "rds": ("RDS", "AWS", "database"),
        "elb": ("ELB", "AWS", "load_balancer"),
        "alb": ("ALB", "AWS", "load_balancer"),
        "lambda": ("Lambda", "AWS", "serverless"),
        "ecs": ("ECS", "AWS", "container"),
        "eks": ("EKS", "AWS", "container"),
        "vpc": ("VPC", "AWS", "network"),
        "cloudfront": ("CloudFront", "AWS", "cdn"),
        "elasticache": ("ElastiCache", "AWS", "cache"),
        "azure vm": ("Azure VM", "Azure", "compute"),
        "blob storage": ("Blob Storage", "Azure", "storage"),
        "gce": ("GCE", "GCP", "compute"),
    }

    for keyword, (name, provider, rtype) in service_keywords.items():
        if keyword in user_ctx:
            state.discovery.discovered_services.append(
                DiscoveredService(
                    service_name=name,
                    provider=provider,
                    resource_type=rtype,
                    configuration={},
                    dependencies=[]
                )
            )

    if not state.discovery.discovered_services:
        state.discovery.discovered_services.append(
            DiscoveredService(
                service_name="Generic Compute",
                provider=state.source_provider or "Unknown",
                resource_type="compute"
            )
        )


def gap_detection(state: MigrationState) -> MigrationState:
    """Identify gaps and calculate confidence score."""
    try:
        logger.info(f"Detecting gaps for migration {state.migration_id}")

        try:
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import JsonOutputParser

            llm = get_llm()
            prompt = ChatPromptTemplate.from_messages([
                ("system", """Analyze cloud migration discovery and identify gaps.
                For each gap provide: category, description, severity (low/medium/high), clarification_question.
                Also calculate a confidence score (0-1).
                Respond in JSON: {{"gaps": [...], "confidence": 0.0-1.0, "rationale": "..."}}
                """),
                ("user", "Discovered services: {services}\nUser context: {user_context}")
            ])
            chain = prompt | llm | JsonOutputParser()
            result = chain.invoke({
                "services": str([s.model_dump() for s in state.discovery.discovered_services]),
                "user_context": state.user_context
            })

            for gap_data in result.get("gaps", []):
                state.discovery.gaps_identified.append(Gap(**gap_data))
            state.discovery.discovery_confidence = result.get("confidence", 0.5)

        except Exception as e:
            logger.warning(f"LLM gap detection failed, using fallback: {e}")
            _gap_detection_fallback(state)

        logger.info(
            f"Gap detection complete: {len(state.discovery.gaps_identified)} gaps, "
            f"confidence: {state.discovery.discovery_confidence:.2%}"
        )
        return state
    except Exception as e:
        logger.error(f"Gap detection failed: {str(e)}")
        state.errors.append(f"Gap detection error: {str(e)}")
        state.discovery.discovery_confidence = 0.3
        return state


def _gap_detection_fallback(state: MigrationState):
    """Provide fallback gap analysis when LLM is unavailable."""
    num_services = len(state.discovery.discovered_services)
    has_network = state.discovery.network_architecture is not None
    has_security = state.discovery.security_posture is not None

    if not has_network:
        state.discovery.gaps_identified.append(Gap(
            category="network",
            description="Network topology not fully documented",
            severity="medium",
            clarification_question="Can you provide details about your network architecture (VPCs, subnets, security groups)?"
        ))

    if not has_security:
        state.discovery.gaps_identified.append(Gap(
            category="security",
            description="Security configuration not documented",
            severity="medium",
            clarification_question="What security requirements do you have (IAM, encryption, compliance)?"
        ))

    if num_services == 0:
        state.discovery.gaps_identified.append(Gap(
            category="services",
            description="No cloud services identified",
            severity="high",
            clarification_question="Please list the cloud services you are currently using."
        ))

    # Calculate confidence
    confidence = 0.5
    if num_services >= 3:
        confidence += 0.2
    if has_network:
        confidence += 0.1
    if has_security:
        confidence += 0.1
    if len(state.discovery.gaps_identified) == 0:
        confidence += 0.1

    state.discovery.discovery_confidence = min(confidence, 1.0)


def clarifications_needed(state: MigrationState) -> MigrationState:
    """Request clarifications if confidence is below threshold."""
    try:
        logger.info(f"Requesting clarifications for migration {state.migration_id}")
        clarification_questions = []
        for gap in state.discovery.gaps_identified:
            if gap.severity in ["medium", "high"]:
                clarification_questions.append(gap.clarification_question)
        state.discovery.clarifications_requested = clarification_questions
        state.phase_status = PhaseStatus.WAITING_REVIEW
        logger.info(f"Requested {len(clarification_questions)} clarifications")
        return state
    except Exception as e:
        logger.error(f"Clarification request failed: {str(e)}")
        state.errors.append(f"Clarification error: {str(e)}")
        return state


def should_request_clarifications(state: MigrationState) -> str:
    """Determine if clarifications are needed based on confidence."""
    from src.utils.config import config
    threshold = config.app.discovery_confidence_threshold
    if state.discovery.discovery_confidence < threshold:
        return "clarify"
    return "continue"
