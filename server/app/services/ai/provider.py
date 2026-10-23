import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMProviderError(Exception):
    """Custom exception raised when an LLM provider fails."""
    pass


class BaseLLMProvider(ABC):
    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        evidence_summary: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Generate grounded assistant response.
        Returns: (response_text, provider_status)
        """
        pass


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", timeout: int = 20):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        evidence_summary: Optional[str] = None,
    ) -> Tuple[str, str]:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        contents: List[Dict[str, Any]] = []

        # Add validated conversation history if provided
        if conversation_history:
            for item in conversation_history[-6:]:
                role = "user" if item.get("role") == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": item.get("content", "")}],
                })

        # Append current user prompt with grounded evidence
        full_user_text = user_message
        if evidence_summary:
            full_user_text += f"\n\n--- VERIFIED BACKEND EVIDENCE (SOURCE OF TRUTH) ---\n{evidence_summary}\n--------------------------------------------------"

        contents.append({
            "role": "user",
            "parts": [{"text": full_user_text}],
        })

        payload = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "temperature": settings.LLM_TEMPERATURE,
                "maxOutputTokens": settings.LLM_MAX_TOKENS,
            },
        }

        try:
            with httpx.Client(timeout=float(self.timeout)) as client:
                res = client.post(endpoint, json=payload, headers={"Content-Type": "application/json"})
                if res.status_code == 429:
                    raise LLMProviderError("Google Gemini rate limit exceeded. Please wait a moment before querying.")
                if res.status_code in [401, 403]:
                    raise LLMProviderError("Google Gemini authentication failed. Invalid API credentials.")
                if res.status_code != 200:
                    logger.error(f"Gemini API returned error {res.status_code}: {res.text}")
                    raise LLMProviderError(f"Gemini API error ({res.status_code}).")

                data = res.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise LLMProviderError("Gemini returned an empty response.")
                first_candidate = candidates[0]
                content_obj = first_candidate.get("content", {})
                parts = content_obj.get("parts", [])
                if not parts:
                    raise LLMProviderError("Gemini candidate has no parts.")
                answer = parts[0].get("text", "").strip()
                return answer, "live_gemini"

        except httpx.TimeoutException:
            logger.warning(f"Gemini request timed out after {self.timeout}s")
            raise LLMProviderError(f"AI Provider timed out after {self.timeout} seconds. The system remains operational.")
        except httpx.RequestError as e:
            logger.error(f"Network error communicating with Gemini: {e}")
            raise LLMProviderError("Unable to reach Google Gemini due to network connectivity issues.")


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", timeout: int = 20):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        evidence_summary: Optional[str] = None,
    ) -> Tuple[str, str]:
        endpoint = "https://api.openai.com/v1/chat/completions"

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            for item in conversation_history[-6:]:
                role = "user" if item.get("role") == "user" else "assistant"
                messages.append({"role": role, "content": item.get("content", "")})

        full_user_text = user_message
        if evidence_summary:
            full_user_text += f"\n\n--- VERIFIED BACKEND EVIDENCE (SOURCE OF TRUTH) ---\n{evidence_summary}\n--------------------------------------------------"

        messages.append({"role": "user", "content": full_user_text})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": settings.LLM_TEMPERATURE,
            "max_tokens": settings.LLM_MAX_TOKENS,
        }

        try:
            with httpx.Client(timeout=float(self.timeout)) as client:
                res = client.post(
                    endpoint,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )
                if res.status_code == 429:
                    raise LLMProviderError("OpenAI rate limit exceeded.")
                if res.status_code in [401, 403]:
                    raise LLMProviderError("OpenAI authentication failed. Invalid API key.")
                if res.status_code != 200:
                    logger.error(f"OpenAI error {res.status_code}: {res.text}")
                    raise LLMProviderError(f"OpenAI API error ({res.status_code}).")

                data = res.json()
                choices = data.get("choices", [])
                if not choices:
                    raise LLMProviderError("OpenAI returned no choices.")
                answer = choices[0].get("message", {}).get("content", "").strip()
                return answer, "live_openai"

        except httpx.TimeoutException:
            raise LLMProviderError(f"OpenAI timed out after {self.timeout} seconds.")
        except httpx.RequestError as e:
            logger.error(f"OpenAI network error: {e}")
            raise LLMProviderError("Unable to reach OpenAI endpoint.")


class MockLLMProvider(BaseLLMProvider):
    """
    High-fidelity, deterministic reasoning synthesizer.
    Used when no external LLM API key is configured or during deterministic automated tests.
    Strictly explains and structures the verified backend evidence.
    """

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        evidence_summary: Optional[str] = None,
    ) -> Tuple[str, str]:
        if not evidence_summary:
            return (
                "I am your Hospital Management Decision-Support Assistant. "
                "I can assist with real-time bed availability, 7-day occupancy trends, "
                "SARIMA capacity forecasts, explainable risk alerts, and inter-ward transfer recommendations. "
                "Please specify a topic or select one of the suggested prompts.",
                "mock_deterministic",
            )

        # Synthesize a clear, grounded hospital management response based on the evidence summary
        lines = [
            "### Hospital Capacity & Decision Support Report",
            "",
            "Based strictly on verified hospital data retrieved from the backend system:",
            "",
            evidence_summary,
            "",
            "---",
            "**Operational Note:** All figures reflect live telemetry and statistical projections. "
            "This assistant provides administrative decision support and does not replace clinical judgment or execute transfers autonomously.",
        ]
        return "\n".join(lines), "mock_deterministic"


def get_llm_provider() -> BaseLLMProvider:
    """Factory to retrieve configured or fallback provider."""
    provider_pref = (settings.LLM_PROVIDER or "auto").strip().lower()

    if provider_pref == "gemini":
        if settings.GEMINI_API_KEY:
            return GeminiProvider(
                api_key=settings.GEMINI_API_KEY,
                model=settings.GEMINI_MODEL,
                timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            )
        logger.info("Gemini provider selected but GEMINI_API_KEY missing. Falling back to MockLLMProvider.")
        return MockLLMProvider()

    if provider_pref == "openai":
        if settings.OPENAI_API_KEY:
            return OpenAIProvider(
                api_key=settings.OPENAI_API_KEY,
                model=settings.OPENAI_MODEL,
                timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            )
        logger.info("OpenAI provider selected but OPENAI_API_KEY missing. Falling back to MockLLMProvider.")
        return MockLLMProvider()

    # "auto" mode
    if settings.GEMINI_API_KEY:
        return GeminiProvider(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
            timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
        )
    if settings.OPENAI_API_KEY:
        return OpenAIProvider(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL,
            timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
        )

    return MockLLMProvider()
