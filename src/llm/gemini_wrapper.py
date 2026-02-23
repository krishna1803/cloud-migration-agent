"""
Google Gemini LangChain Wrapper for OCI Generative AI Service

Provides a LangChain BaseChatModel subclass that drives Google Gemini models
via the native OCI Generative AI SDK.  Fully compatible with LangChain LCEL
pipelines (prompt | llm | parser) and drops in wherever ChatOCIGenAI was used.
"""
import time
from typing import Any, Iterator, List, Optional

import oci
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field, PrivateAttr

from src.utils.config import config
from src.utils.logger import logger

_MAX_PREVIEW = 800  # chars for log previews


class GeminiLangChainWrapper(BaseChatModel):
    """
    LangChain BaseChatModel backed by Google Gemini via OCI Generative AI.

    Works transparently in LCEL chains::

        chain = ChatPromptTemplate.from_messages([...]) | GeminiLangChainWrapper() | parser
        result = chain.invoke({...})

    Configuration is read from the shared ``config`` singleton (env vars /
    ``.env`` file).  Individual parameters can be overridden at construction time.

    Environment variables
    ---------------------
    OCI_GENAI_MODEL_ID      – Gemini model OCID
    OCI_GENAI_ENDPOINT      – OCI GenAI inference endpoint
    OCI_COMPARTMENT_ID      – OCI compartment OCID
    OCI_GENAI_TEMPERATURE   – sampling temperature (default 0.1)
    OCI_GENAI_MAX_TOKENS    – max output tokens (default 4096)
    OCI_GENAI_TOP_P         – nucleus-sampling p (default 0.95)
    OCI_GENAI_TOP_K         – top-k (default 1)
    """

    # ── Pydantic fields (configurable via constructor or env) ────────────────
    model_id: str = Field(default_factory=lambda: config.genai.model_id)
    compartment_id: str = Field(default_factory=lambda: config.oci.compartment_id)
    service_endpoint: str = Field(default_factory=lambda: config.genai.endpoint)
    temperature: float = Field(default_factory=lambda: config.genai.temperature)
    max_tokens: int = Field(default_factory=lambda: config.genai.max_tokens)
    top_p: float = Field(default_factory=lambda: config.genai.top_p)
    top_k: int = Field(default_factory=lambda: config.genai.top_k)

    # ── Private OCI client (not part of model serialisation) ─────────────────
    _client: Any = PrivateAttr(default=None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._setup_client()

    # ── Required LangChain property ──────────────────────────────────────────
    @property
    def _llm_type(self) -> str:
        return "oci_gemini"

    # ── OCI client initialisation (mirrors OCIGenAI._setup_client) ───────────
    def _setup_client(self) -> None:
        try:
            oci_config = oci.config.from_file()

            # Allow env-var overrides (same pattern as OCIGenAI)
            if config.oci.region:
                oci_config["region"] = config.oci.region
            if config.oci.tenancy_id:
                oci_config["tenancy"] = config.oci.tenancy_id
            if config.oci.user_id:
                oci_config["user"] = config.oci.user_id
            if config.oci.fingerprint:
                oci_config["fingerprint"] = config.oci.fingerprint
            if config.oci.private_key_path:
                oci_config["key_file"] = config.oci.private_key_path

            self._client = oci.generative_ai_inference.GenerativeAiInferenceClient(
                config=oci_config,
                service_endpoint=self.service_endpoint,
                retry_strategy=oci.retry.NoneRetryStrategy(),
                timeout=(10, 240),
            )
            logger.info(
                "GeminiLangChainWrapper initialised",
                extra={
                    "model_id": self.model_id,
                    "endpoint": self.service_endpoint,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                },
            )
        except Exception as exc:
            logger.error(f"Failed to initialise OCI Gemini client: {exc}")
            raise

    # ── Core LangChain implementation ─────────────────────────────────────────
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager=None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        Convert LangChain messages → OCI GenericChatRequest → AIMessage.

        This is the single method that LangChain calls for every ``invoke``,
        ``stream``, and LCEL ``|`` pipeline execution.
        """
        t0 = time.time()
        prompt_preview = self._messages_preview(messages)
        logger.info(
            "[LLM] OCI Gemini request",
            extra={
                "event_type": "llm_request",
                "model_id": self.model_id,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "message_count": len(messages),
                "prompt_preview": prompt_preview,
            },
        )

        try:
            oci_messages = self._convert_messages_to_oci(messages)
            oci_response = self._call_oci_api(oci_messages)
            response_text = self._extract_text(oci_response)

            duration_ms = (time.time() - t0) * 1000
            logger.info(
                f"[LLM] OCI Gemini response [{duration_ms:.0f}ms]",
                extra={
                    "event_type": "llm_response",
                    "model_id": self.model_id,
                    "duration_ms": round(duration_ms, 1),
                    "response_chars": len(response_text),
                    "response_preview": response_text[:_MAX_PREVIEW],
                },
            )

            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content=response_text))]
            )

        except Exception as exc:
            duration_ms = (time.time() - t0) * 1000
            logger.error(
                f"[LLM] OCI Gemini call failed [{duration_ms:.0f}ms]: {exc}",
                extra={
                    "event_type": "llm_error",
                    "model_id": self.model_id,
                    "duration_ms": round(duration_ms, 1),
                    "error": str(exc),
                },
            )
            raise

    # ── Message conversion ────────────────────────────────────────────────────
    def _convert_messages_to_oci(self, messages: List[BaseMessage]) -> List[Any]:
        """
        Convert LangChain messages to OCI GenericChatRequest message format.

        Gemini (via OCI GenericChatRequest) does not support a first-class
        SYSTEM role, so leading SystemMessages are merged into the content of
        the first USER message.
        """
        # Separate leading system message (if any)
        system_prefix = ""
        remaining = list(messages)
        if remaining and remaining[0].type == "system":
            system_prefix = remaining.pop(0).content

        oci_messages = []
        for msg in remaining:
            text_content = oci.generative_ai_inference.models.TextContent()
            text_content.text = msg.content

            oci_msg = oci.generative_ai_inference.models.Message()
            oci_msg.role = self._map_role(msg.type)
            oci_msg.content = [text_content]
            oci_messages.append(oci_msg)

        # Prepend system prefix to the first USER message
        if system_prefix and oci_messages:
            first = oci_messages[0]
            first.content[0].text = f"{system_prefix}\n\n{first.content[0].text}"

        # Gemini requires at least one USER message
        if not oci_messages:
            fallback = oci.generative_ai_inference.models.TextContent()
            fallback.text = system_prefix or "Hello"
            placeholder = oci.generative_ai_inference.models.Message()
            placeholder.role = "USER"
            placeholder.content = [fallback]
            oci_messages.append(placeholder)

        return oci_messages

    @staticmethod
    def _map_role(langchain_type: str) -> str:
        return {"human": "USER", "system": "SYSTEM", "ai": "ASSISTANT"}.get(
            langchain_type, "USER"
        )

    # ── OCI API call ──────────────────────────────────────────────────────────
    def _call_oci_api(self, oci_messages: List[Any]) -> Any:
        chat_request = oci.generative_ai_inference.models.GenericChatRequest()
        chat_request.api_format = (
            oci.generative_ai_inference.models.BaseChatRequest.API_FORMAT_GENERIC
        )
        chat_request.messages = oci_messages
        chat_request.max_tokens = self.max_tokens
        chat_request.temperature = self.temperature
        chat_request.top_p = self.top_p
        chat_request.top_k = self.top_k
        chat_request.frequency_penalty = 0
        chat_request.presence_penalty = 0

        chat_detail = oci.generative_ai_inference.models.ChatDetails()
        chat_detail.serving_mode = oci.generative_ai_inference.models.OnDemandServingMode(
            model_id=self.model_id
        )
        chat_detail.chat_request = chat_request
        chat_detail.compartment_id = self.compartment_id

        return self._client.chat(chat_detail)

    # ── Response parsing ──────────────────────────────────────────────────────
    @staticmethod
    def _extract_text(oci_response: Any) -> str:
        try:
            chat_resp = oci_response.data.chat_response
            choices = chat_resp.choices
            if choices:
                parts = choices[0].message.content
                return "".join(
                    p.text for p in parts if hasattr(p, "text")
                )
        except Exception as exc:
            logger.warning(f"Could not parse OCI Gemini response: {exc}")
        return ""

    # ── Logging helper ────────────────────────────────────────────────────────
    @staticmethod
    def _messages_preview(messages: List[BaseMessage]) -> str:
        parts = []
        for m in messages:
            tag = m.type.upper()
            parts.append(f"[{tag}] {m.content[:200]}")
        return " | ".join(parts)[:_MAX_PREVIEW]
