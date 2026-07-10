"""
=============================================================================
SmartKrishi - IBM watsonx.ai Service
Granite model integration for AI-powered farming advice
=============================================================================
"""

import os
import time
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Models that use text_chat endpoint vs text_generation endpoint.
# text_chat is preferred — it's the modern messages-based API.
_CHAT_ONLY_MODELS = {
    "meta-llama/llama-3-1-8b",
    "meta-llama/llama-3-1-70b-instruct",
    "meta-llama/llama-3-2-1b-instruct",
    "meta-llama/llama-3-2-3b-instruct",
}


class WatsonxService:
    """
    IBM watsonx.ai Granite model service.
    Automatically uses text_chat endpoint when the model supports it,
    falling back to text_generation for models that only support that.
    """

    def __init__(self):
        self.api_key = os.getenv("IBM_CLOUD_API_KEY")
        self.project_id = os.getenv("WATSONX_PROJECT_ID")
        self.url = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
        self.model_id = os.getenv("WATSONX_MODEL_ID", "ibm/granite-8b-code-instruct")
        self.client = None
        self._initialized = False
        self._use_chat_endpoint = True  # granite-8b-code-instruct supports text_chat

    def initialize(self) -> bool:
        """Initialize IBM watsonx.ai client."""
        if not self.api_key or not self.project_id:
            logger.warning("IBM watsonx.ai credentials not configured. Running in demo mode.")
            return False

        try:
            import warnings
            from ibm_watsonx_ai import Credentials
            from ibm_watsonx_ai.foundation_models import ModelInference

            credentials = Credentials(
                url=self.url,
                api_key=self.api_key
            )

            # Suppress lifecycle deprecation warnings — we know the model
            # state; the app will still work until withdrawal date.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.client = ModelInference(
                    model_id=self.model_id,
                    credentials=credentials,
                    project_id=self.project_id,
                )

            # Detect which endpoint to use based on model ID
            # Models in _CHAT_ONLY_MODELS do NOT support text_generation
            self._use_chat_endpoint = self.model_id not in _CHAT_ONLY_MODELS

            self._initialized = True
            logger.info(
                f"watsonx.ai initialized | model: {self.model_id} | "
                f"endpoint: {'text_chat' if self._use_chat_endpoint else 'text_generation'}"
            )
            return True

        except ImportError:
            logger.error("ibm-watsonx-ai package not installed. Run: pip install ibm-watsonx-ai")
            return False
        except Exception as e:
            logger.error(f"watsonx.ai initialization failed: {e}")
            return False

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = None,
        temperature: float = None,
        stop_sequences: List[str] = None
    ) -> Dict:
        """
        Generate a response using text_chat (preferred) or text_generation.

        Returns:
            dict with keys: text, tokens_used, model, success, error
        """
        max_tokens = max_tokens or int(os.getenv("AGENT_MAX_TOKENS", 1024))
        temperature = temperature or float(os.getenv("AGENT_TEMPERATURE", 0.7))

        if not self._initialized:
            return self._demo_response(user_message)

        if self._use_chat_endpoint:
            return self._generate_chat(system_prompt, user_message, max_tokens, temperature)
        else:
            return self._generate_text(system_prompt, user_message, max_tokens, temperature, stop_sequences)

    # ── text_chat endpoint (granite-8b-code-instruct, llama-3-3-70b-instruct) ──

    def _generate_chat(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        temperature: float
    ) -> Dict:
        """Use the text_chat (messages) API — better instruction following."""
        import warnings
        start_time = time.time()

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ]

            params = {
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                response = self.client.chat(
                    messages=messages,
                    params=params
                )

            elapsed_ms = int((time.time() - start_time) * 1000)

            # text_chat response shape:
            # {"choices": [{"message": {"role": "assistant", "content": "..."}}], "usage": {...}}
            choices = response.get("choices") or []
            if choices:
                content = choices[0].get("message", {}).get("content", "").strip()
                usage   = response.get("usage", {})
                tokens  = usage.get("completion_tokens", 0)

                content = self._clean_response(content)
                return {
                    "text": content,
                    "tokens_used": tokens,
                    "model": self.model_id,
                    "response_time_ms": elapsed_ms,
                    "success": True,
                    "error": None
                }

            return {
                "text": "I apologize, I couldn't generate a response. Please try again.",
                "tokens_used": 0,
                "model": self.model_id,
                "success": False,
                "error": "Empty response from chat endpoint"
            }

        except Exception as e:
            logger.error(f"watsonx chat error: {e}")
            return self._handle_error(e)

    # ── text_generation endpoint (fallback for generation-only models) ──────────

    def _generate_text(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        temperature: float,
        stop_sequences: List[str] = None
    ) -> Dict:
        """Use the text_generation API with Granite prompt template."""
        start_time = time.time()

        try:
            params = {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "decoding_method": "sample" if temperature > 0 else "greedy",
                "repetition_penalty": 1.1,
                "stop_sequences": stop_sequences or ["<|endoftext|>"],
            }

            prompt = self._build_granite_prompt(system_prompt, user_message)
            response = self.client.generate(prompt=prompt, params=params)

            elapsed_ms = int((time.time() - start_time) * 1000)

            if response and "results" in response and response["results"]:
                result = response["results"][0]
                text   = self._clean_response(result.get("generated_text", "").strip())
                tokens = result.get("generated_token_count", 0)
                return {
                    "text": text,
                    "tokens_used": tokens,
                    "model": self.model_id,
                    "response_time_ms": elapsed_ms,
                    "success": True,
                    "error": None
                }

            return {
                "text": "I apologize, I couldn't generate a response. Please try again.",
                "tokens_used": 0,
                "model": self.model_id,
                "success": False,
                "error": "Empty response from generation endpoint"
            }

        except Exception as e:
            logger.error(f"watsonx generation error: {e}")
            return self._handle_error(e)

    def _handle_error(self, e: Exception) -> Dict:
        error_msg = str(e)
        if "429" in error_msg or "rate limit" in error_msg.lower():
            return {
                "text": "I'm currently handling many requests. Please wait a moment and try again.",
                "tokens_used": 0,
                "success": False,
                "error": "rate_limit"
            }
        # If chat endpoint fails with model_no_support, retry with text_generation
        if "model_no_support" in error_msg and self._use_chat_endpoint:
            logger.warning("Chat endpoint unsupported, falling back to text_generation")
            self._use_chat_endpoint = False
        return {
            "text": "I encountered a technical issue. Please try again or contact support.",
            "tokens_used": 0,
            "success": False,
            "error": error_msg
        }

    def _build_granite_prompt(self, system_prompt: str, user_message: str) -> str:
        """
        Build Granite-formatted prompt.
        Granite models use a specific chat template.
        """
        prompt = f"""<|system|>
{system_prompt}
<|user|>
{user_message}
<|assistant|>
"""
        return prompt

    def _clean_response(self, text: str) -> str:
        """Remove Granite-specific artifacts from generated text."""
        # Remove any leftover special tokens
        for token in ["<|system|>", "<|user|>", "<|assistant|>", "<|endoftext|>"]:
            text = text.replace(token, "")
        return text.strip()

    def _demo_response(self, user_message: str) -> Dict:
        """Fallback demo response when API is not configured."""
        responses = {
            "default": """🌾 **KrishiMitra Demo Mode**

I'm currently running in demo mode (IBM watsonx.ai not configured).

To enable full AI capabilities:
1. Add your `IBM_CLOUD_API_KEY` to the `.env` file
2. Add your `WATSONX_PROJECT_ID` 
3. Restart the application

**Your question was:** "{}"

In production, I would provide detailed farming advice powered by IBM Granite AI models with:
✅ Crop disease diagnosis
✅ Soil analysis interpretation  
✅ Weather-based farming advice
✅ Government scheme information
✅ Mandi price insights
✅ Multilingual support (Hindi, Tamil, Telugu, and more)
""".format(user_message[:100])
        }

        # Simple keyword matching for demo
        lower = user_message.lower()
        if any(w in lower for w in ["disease", "blight", "rust", "fungal"]):
            demo_text = """**Demo: Disease Diagnosis**

For proper disease diagnosis, please configure IBM watsonx.ai credentials.

**General guidance:** 
- Look for lesion patterns, color changes, and affected plant parts
- Check weather conditions (humidity, temperature) 
- Consult ICAR disease identification guides
- Call Kisan Call Centre: **1800-180-1551** for expert advice"""
        elif any(w in lower for w in ["scheme", "yojana", "subsidy", "pm-kisan"]):
            demo_text = """**Demo: Government Schemes**

Key schemes for Indian farmers:
• **PM-KISAN**: ₹6,000/year income support - pmkisan.gov.in
• **PMFBY**: Crop insurance at 2% premium - pmfby.gov.in
• **KCC**: Low-interest crop loans at 4%
• **PMKSY**: Irrigation subsidy up to 55%

Configure watsonx.ai for detailed, personalized scheme information."""
        else:
            demo_text = responses["default"]

        return {
            "text": demo_text,
            "tokens_used": 0,
            "model": "demo-mode",
            "success": True,
            "error": None,
            "is_demo": True
        }

    def is_ready(self) -> bool:
        """Check if the service is properly initialized."""
        return self._initialized


# =============================================================================
# TRANSLATION SERVICE
# =============================================================================
class TranslationService:
    """Simple translation service using LibreTranslate or Google Translate."""

    SUPPORTED_LANGUAGES = {
        "en": "English",
        "hi": "Hindi",
        "ta": "Tamil",
        "te": "Telugu",
        "kn": "Kannada",
        "bn": "Bengali",
        "mr": "Marathi",
        "gu": "Gujarati",
        "pa": "Punjabi",
        "ml": "Malayalam",
        "or": "Odia",
        "ur": "Urdu"
    }

    def __init__(self):
        self.api_url = os.getenv("TRANSLATE_API_URL", "https://libretranslate.com")
        self.api_key = os.getenv("TRANSLATE_API_KEY", "")

    def detect_language(self, text: str) -> str:
        """Detect language from text. Returns ISO code."""
        import re

        # Devanagari (Hindi/Marathi)
        if re.search(r'[\u0900-\u097F]', text):
            return "hi"
        # Tamil
        if re.search(r'[\u0B80-\u0BFF]', text):
            return "ta"
        # Telugu
        if re.search(r'[\u0C00-\u0C7F]', text):
            return "te"
        # Kannada
        if re.search(r'[\u0C80-\u0CFF]', text):
            return "kn"
        # Bengali
        if re.search(r'[\u0980-\u09FF]', text):
            return "bn"
        # Gujarati
        if re.search(r'[\u0A80-\u0AFF]', text):
            return "gu"
        # Punjabi (Gurmukhi)
        if re.search(r'[\u0A00-\u0A7F]', text):
            return "pa"
        # Malayalam
        if re.search(r'[\u0D00-\u0D7F]', text):
            return "ml"
        # Urdu/Arabic script
        if re.search(r'[\u0600-\u06FF]', text):
            return "ur"

        return "en"

    def translate(self, text: str, target_lang: str, source_lang: str = "auto") -> str:
        """Translate text to target language. Returns original if fails."""
        if target_lang == "en" and source_lang == "en":
            return text
        if not self.api_url or not text:
            return text

        try:
            import requests
            response = requests.post(
                f"{self.api_url}/translate",
                json={
                    "q": text,
                    "source": source_lang,
                    "target": target_lang,
                    "api_key": self.api_key
                },
                timeout=10
            )
            if response.ok:
                return response.json().get("translatedText", text)
        except Exception as e:
            logger.warning(f"Translation failed: {e}")

        return text


# Singletons
watsonx_service = WatsonxService()
translation_service = TranslationService()
