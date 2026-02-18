"""
OCI Generative AI Service integration for LangChain.

Provides LLM and embedding models using OCI GenAI.
"""

import time
import oci
from typing import Any, List, Optional, Dict
from langchain_core.language_models.llms import LLM
from langchain_core.embeddings import Embeddings
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from pydantic import Field

from src.utils.config import config
from src.utils.logger import logger

_MAX_PREVIEW = 800   # characters to log for prompt / response previews


class OCIGenAI(LLM):
    """
    OCI Generative AI LLM wrapper for LangChain.
    
    Uses Cohere Command R+ model via OCI GenAI Service.
    """
    
    model_id: str = Field(default=config.genai.model_id)
    max_tokens: int = Field(default=config.genai.max_tokens)
    temperature: float = Field(default=config.genai.temperature)
    compartment_id: str = Field(default=config.oci.compartment_id)
    
    _client: Any = None
    
    def __init__(self, **kwargs):
        """Initialize OCI GenAI client"""
        super().__init__(**kwargs)
        self._setup_client()
    
    def _setup_client(self):
        """Set up OCI GenAI client with authentication"""
        try:
            # Load OCI config
            oci_config = oci.config.from_file()
            
            # Override with environment variables if provided
            if config.oci.region:
                oci_config['region'] = config.oci.region
            if config.oci.tenancy_id:
                oci_config['tenancy'] = config.oci.tenancy_id
            if config.oci.user_id:
                oci_config['user'] = config.oci.user_id
            if config.oci.fingerprint:
                oci_config['fingerprint'] = config.oci.fingerprint
            if config.oci.private_key_path:
                oci_config['key_file'] = config.oci.private_key_path
            
            # Create GenAI client
            self._client = oci.generative_ai_inference.GenerativeAiInferenceClient(
                config=oci_config,
                service_endpoint=config.genai.endpoint
            )
            
            logger.info(f"OCI GenAI client initialized with model: {self.model_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize OCI GenAI client: {str(e)}")
            raise
    
    @property
    def _llm_type(self) -> str:
        """Return type of LLM"""
        return "oci_genai"
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """
        Call OCI GenAI model.

        Args:
            prompt: The prompt to send to the model
            stop: Stop sequences
            run_manager: Callback manager
            **kwargs: Additional arguments

        Returns:
            Model response text
        """
        t0 = time.time()
        max_tok = kwargs.get("max_tokens", self.max_tokens)
        temp = kwargs.get("temperature", self.temperature)

        logger.info(
            "[LLM] OCI GenAI request",
            extra={
                "event_type": "llm_request",
                "model_id": self.model_id,
                "max_tokens": max_tok,
                "temperature": temp,
                "prompt_chars": len(prompt),
                "prompt_preview": prompt[:_MAX_PREVIEW],
            },
        )

        try:
            # Prepare request
            chat_request = oci.generative_ai_inference.models.CohereChatRequest()
            chat_request.message = prompt
            chat_request.max_tokens = max_tok
            chat_request.temperature = temp

            if stop:
                chat_request.stop_sequences = stop

            # Create chat details
            chat_detail = oci.generative_ai_inference.models.ChatDetails()
            chat_detail.serving_mode = oci.generative_ai_inference.models.OnDemandServingMode(
                model_id=self.model_id
            )
            chat_detail.compartment_id = self.compartment_id
            chat_detail.chat_request = chat_request

            # Make request
            chat_response = self._client.chat(chat_detail)

            # Extract response text
            response_text = chat_response.data.chat_response.text

            duration_ms = (time.time() - t0) * 1000
            logger.info(
                f"[LLM] OCI GenAI response [{duration_ms:.0f}ms]",
                extra={
                    "event_type": "llm_response",
                    "model_id": self.model_id,
                    "duration_ms": round(duration_ms, 1),
                    "response_chars": len(response_text),
                    "response_preview": response_text[:_MAX_PREVIEW],
                },
            )

            return response_text

        except Exception as e:
            duration_ms = (time.time() - t0) * 1000
            logger.error(
                f"[LLM] OCI GenAI call failed [{duration_ms:.0f}ms]: {e}",
                extra={
                    "event_type": "llm_error",
                    "model_id": self.model_id,
                    "duration_ms": round(duration_ms, 1),
                    "error": str(e),
                },
            )
            raise
    
    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Async call - not implemented, falls back to sync"""
        return self._call(prompt, stop, run_manager, **kwargs)


class OCIGenAIEmbeddings(Embeddings):
    """
    OCI Generative AI Embeddings wrapper for LangChain.
    
    Uses Cohere Embed English v3.0 model via OCI GenAI Service.
    """
    
    model_id: str = Field(default=config.genai.embedding_model_id)
    compartment_id: str = Field(default=config.oci.compartment_id)
    truncate: str = Field(default="END")
    
    _client: Any = None
    
    def __init__(self, **kwargs):
        """Initialize OCI GenAI Embeddings client"""
        super().__init__(**kwargs)
        self._setup_client()
    
    def _setup_client(self):
        """Set up OCI GenAI client"""
        try:
            # Load OCI config
            oci_config = oci.config.from_file()
            
            # Override with environment variables
            if config.oci.region:
                oci_config['region'] = config.oci.region
            if config.oci.tenancy_id:
                oci_config['tenancy'] = config.oci.tenancy_id
            if config.oci.user_id:
                oci_config['user'] = config.oci.user_id
            if config.oci.fingerprint:
                oci_config['fingerprint'] = config.oci.fingerprint
            if config.oci.private_key_path:
                oci_config['key_file'] = config.oci.private_key_path
            
            # Create GenAI client
            self._client = oci.generative_ai_inference.GenerativeAiInferenceClient(
                config=oci_config,
                service_endpoint=config.genai.endpoint
            )
            
            logger.info(f"OCI GenAI Embeddings initialized with model: {self.model_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize OCI GenAI Embeddings: {str(e)}")
            raise
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of documents.
        
        Args:
            texts: List of text documents to embed
            
        Returns:
            List of embeddings (each embedding is a list of floats)
        """
        try:
            # Prepare request
            embed_text_details = oci.generative_ai_inference.models.EmbedTextDetails()
            embed_text_details.serving_mode = oci.generative_ai_inference.models.OnDemandServingMode(
                model_id=self.model_id
            )
            embed_text_details.compartment_id = self.compartment_id
            embed_text_details.inputs = texts
            embed_text_details.truncate = self.truncate
            embed_text_details.input_type = "SEARCH_DOCUMENT"
            
            # Make request
            embed_text_response = self._client.embed_text(embed_text_details)
            
            # Extract embeddings
            embeddings = [
                embedding for embedding in embed_text_response.data.embeddings
            ]
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Document embedding failed: {str(e)}")
            raise
    
    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single query.
        
        Args:
            text: Query text to embed
            
        Returns:
            Embedding vector
        """
        try:
            # Prepare request
            embed_text_details = oci.generative_ai_inference.models.EmbedTextDetails()
            embed_text_details.serving_mode = oci.generative_ai_inference.models.OnDemandServingMode(
                model_id=self.model_id
            )
            embed_text_details.compartment_id = self.compartment_id
            embed_text_details.inputs = [text]
            embed_text_details.truncate = self.truncate
            embed_text_details.input_type = "SEARCH_QUERY"
            
            # Make request
            embed_text_response = self._client.embed_text(embed_text_details)
            
            # Extract embedding
            embedding = embed_text_response.data.embeddings[0]
            
            return embedding
            
        except Exception as e:
            logger.error(f"Query embedding failed: {str(e)}")
            raise


# Convenience functions
def get_llm(**kwargs) -> OCIGenAI:
    """Get OCI GenAI LLM instance"""
    return OCIGenAI(**kwargs)


def get_embeddings(**kwargs) -> OCIGenAIEmbeddings:
    """Get OCI GenAI Embeddings instance"""
    return OCIGenAIEmbeddings(**kwargs)
