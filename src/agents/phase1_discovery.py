"""
Phase 1: Discovery - Agent nodes for discovering source cloud architecture.

This phase extracts and analyzes source cloud architecture from
evidence (documents, BoM, user input).
"""

from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from src.models.state_schema import MigrationState, PhaseStatus, Gap
from src.utils.oci_genai import get_llm
from src.utils.document_processor import DocumentProcessor, extract_evidence_from_documents
from src.utils.logger import logger


# Phase 1 Node 1: Intake Migration Request
def intake_plan(state: MigrationState) -> MigrationState:
    """
    Intake migration request and initialize workflow.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with intake complete
    """
    try:
        logger.info(f"Starting intake for migration {state.migration_id}")
        
        # Update phase
        state.current_phase = "discovery"
        state.phase_status = PhaseStatus.IN_PROGRESS
        
        # Add intake message
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


# Phase 1 Node 2: Knowledge Base Enrichment
def kb_enrich_discovery(state: MigrationState) -> MigrationState:
    """
    Enrich discovery with knowledge base intelligence.
    
    This would typically query the KB for migration patterns,
    best practices, and known mappings.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with KB enrichment
    """
    try:
        logger.info(f"KB enrichment for migration {state.migration_id}")
        
        # TODO: Implement KB query via MCP tool
        # For now, add placeholder
        state.messages.append({
            "role": "system",
            "content": "Knowledge base enrichment completed"
        })
        
        return state
        
    except Exception as e:
        logger.error(f"KB enrichment failed: {str(e)}")
        state.errors.append(f"KB enrichment error: {str(e)}")
        return state


# Phase 1 Node 3: Document Ingestion
def document_ingestion(state: MigrationState) -> MigrationState:
    """
    Process uploaded documents (PDF, DOCX, diagrams).
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with processed documents
    """
    try:
        logger.info(f"Processing documents for migration {state.migration_id}")
        
        if not state.uploaded_documents:
            logger.warning("No documents to process")
            return state
        
        # Process documents
        processor = DocumentProcessor()
        processed_docs = processor.process_multiple_documents(state.uploaded_documents)
        
        # Store processed documents in messages for now
        for doc in processed_docs:
            if not doc.get("error"):
                state.messages.append({
                    "role": "system",
                    "content": f"Processed {doc['file_type']}: {doc['file_path']}"
                })
        
        logger.info(f"Processed {len(processed_docs)} documents")
        return state
        
    except Exception as e:
        logger.error(f"Document ingestion failed: {str(e)}")
        state.errors.append(f"Document ingestion error: {str(e)}")
        return state


# Phase 1 Node 4: BOM Analysis
def bom_analysis(state: MigrationState) -> MigrationState:
    """
    Parse Excel/CSV Bill of Materials for cost data.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with BOM analysis
    """
    try:
        logger.info(f"Analyzing BOM for migration {state.migration_id}")
        
        if not state.bom_file:
            logger.warning("No BOM file provided")
            return state
        
        # Process BOM
        processor = DocumentProcessor()
        bom_data = processor.process_excel_bom(state.bom_file)
        
        # Extract resources
        for resource in bom_data.get("resources", []):
            state.messages.append({
                "role": "system",
                "content": f"BOM resource: {resource.get('name', 'Unknown')}"
            })
        
        logger.info(
            f"Analyzed BOM: {bom_data['num_resources']} resources, "
            f"${bom_data['total_monthly_cost']:.2f}/month"
        )
        
        return state
        
    except Exception as e:
        logger.error(f"BOM analysis failed: {str(e)}")
        state.errors.append(f"BOM analysis error: {str(e)}")
        return state


# Phase 1 Node 5: Extract Evidence
def extract_evidence(state: MigrationState) -> MigrationState:
    """
    Consolidate evidence from all sources using LLM.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with consolidated evidence
    """
    try:
        logger.info(f"Extracting evidence for migration {state.migration_id}")
        
        # Get LLM
        llm = get_llm()
        
        # Create extraction prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert cloud architect analyzing migration evidence.
            Extract the following information from the provided context:
            
            1. Cloud services being used (compute, storage, database, networking)
            2. Network architecture (VPCs, subnets, security groups)
            3. Compute resources (instance types, sizes, counts)
            4. Storage resources (types, sizes, IOPS)
            5. Security configuration (IAM, policies, encryption)
            
            Respond in JSON format with these top-level keys:
            - services: list of service objects
            - network: network architecture object
            - compute: list of compute resources
            - storage: list of storage resources
            - security: security posture object
            
            Be thorough but conservative. Only include information you can verify.
            """),
            ("user", "Context: {context}\n\nUser provided: {user_context}")
        ])
        
        # Prepare context from messages
        context = "\n".join([msg["content"] for msg in state.messages])
        
        # Extract evidence
        chain = prompt | llm | JsonOutputParser()
        evidence = chain.invoke({
            "context": context,
            "user_context": state.user_context
        })
        
        # Update discovery state
        state.discovery.discovered_services = evidence.get("services", [])
        
        logger.info(
            f"Extracted evidence: {len(state.discovery.discovered_services)} services"
        )
        
        return state
        
    except Exception as e:
        logger.error(f"Evidence extraction failed: {str(e)}")
        state.errors.append(f"Evidence extraction error: {str(e)}")
        return state


# Phase 1 Node 6: Gap Detection
def gap_detection(state: MigrationState) -> MigrationState:
    """
    Identify gaps and calculate confidence score.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state with gaps identified and confidence score
    """
    try:
        logger.info(f"Detecting gaps for migration {state.migration_id}")
        
        llm = get_llm()
        
        # Create gap detection prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are analyzing a cloud migration discovery phase.
            Identify any missing or ambiguous information that could affect migration success.
            
            Review the discovered architecture and identify gaps in:
            1. Service configurations
            2. Network topology
            3. Security requirements
            4. Compliance needs
            5. Performance requirements
            6. Data migration strategy
            
            For each gap, provide:
            - category: the area of concern
            - description: what's missing
            - severity: low/medium/high
            - clarification_question: question to ask the user
            
            Also calculate a confidence score (0-1) based on completeness.
            
            Respond in JSON format:
            {{
                "gaps": [list of gap objects],
                "confidence": 0.0-1.0,
                "rationale": "explanation"
            }}
            """),
            ("user", "Discovered architecture: {discovery}\n\nUser context: {user_context}")
        ])
        
        # Detect gaps
        chain = prompt | llm | JsonOutputParser()
        result = chain.invoke({
            "discovery": str(state.discovery.dict()),
            "user_context": state.user_context
        })
        
        # Update state with gaps
        gaps = result.get("gaps", [])
        for gap_data in gaps:
            gap = Gap(**gap_data)
            state.discovery.gaps_identified.append(gap)
        
        # Update confidence
        state.discovery.discovery_confidence = result.get("confidence", 0.5)
        
        logger.info(
            f"Gap detection complete: {len(gaps)} gaps found, "
            f"confidence: {state.discovery.discovery_confidence:.2%}"
        )
        
        return state
        
    except Exception as e:
        logger.error(f"Gap detection failed: {str(e)}")
        state.errors.append(f"Gap detection error: {str(e)}")
        # Set default low confidence on error
        state.discovery.discovery_confidence = 0.3
        return state


# Phase 1 Node 7: Clarifications Needed (Conditional)
def clarifications_needed(state: MigrationState) -> MigrationState:
    """
    Request clarifications if confidence is below threshold.
    
    Args:
        state: Current migration state
        
    Returns:
        Updated state waiting for clarifications
    """
    try:
        logger.info(f"Requesting clarifications for migration {state.migration_id}")
        
        # Generate clarification questions from gaps
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


# Conditional edge: Should request clarifications?
def should_request_clarifications(state: MigrationState) -> str:
    """
    Determine if clarifications are needed based on confidence.
    
    Args:
        state: Current migration state
        
    Returns:
        "clarify" if confidence < 80%, else "continue"
    """
    from src.utils.config import config
    
    threshold = config.app.discovery_confidence_threshold
    
    if state.discovery.discovery_confidence < threshold:
        return "clarify"
    else:
        return "continue"
