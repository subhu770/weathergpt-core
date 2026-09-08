"""
WeatherGPT - Bhashini Speech-to-Speech (ASR & TTS) Service
Ministry of Earth Sciences (MoES / SIH26068)

Asynchronous integration with Government of India's Bhashini (National Language Translation Mission)
Dhruva pipeline for multilingual Automated Speech Recognition (ASR) and Text-to-Speech (TTS).
Includes robust fault-tolerance, connection pooling, and seamless fallback signaling.
"""

import logging
from typing import Optional, Dict, Any
import httpx

from app.config import settings

logger = logging.getLogger("WeatherGPT.BhashiniService")


# Language mapping to standard Bhashini / ISO 639-1 language codes
LANGUAGE_MAP: Dict[str, str] = {
    # English mappings
    "en": "en",
    "eng": "en",
    "english": "en",
    "en-in": "en",
    "en-us": "en",
    "en-gb": "en",

    # Hindi mappings
    "hi": "hi",
    "hin": "hi",
    "hindi": "hi",
    "hi-in": "hi",
    "हिन्दी": "hi",
    "हिंदी": "hi",

    # Odia mappings
    "or": "or",
    "ori": "or",
    "odi": "or",
    "odia": "or",
    "oriya": "or",
    "or-in": "or",
    "ଓଡ଼ିଆ": "or",
    "ଓଡିଆ": "or",
}


class BhashiniService:
    """
    Production Bhashini Speech Service providing ASR and TTS capabilities
    via the Government of India Bhashini Dhruva Pipeline inference gateway.
    """

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily initialize and reuse an asynchronous HTTP connection pool."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.bhashini_timeout_seconds),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                headers={
                    "User-Agent": f"WeatherGPT-MoES/{settings.app_version} (SIH26068; Bhashini Speech Client)"
                }
            )
        return self._client

    async def close(self):
        """Cleanly terminate the underlying HTTP connection pool."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def normalize_language(self, language: Optional[str]) -> str:
        """
        Normalize input language names and variants to standard Bhashini codes ('en', 'hi', 'or').
        Defaults to 'en' (English) if unknown or unspecified.
        """
        if not language:
            return "en"
        clean = language.strip().lower()
        return LANGUAGE_MAP.get(clean, "en")

    def is_configured(self) -> bool:
        """Check if Bhashini authorization credentials are present."""
        return bool(settings.bhashini_api_key and settings.bhashini_api_key.strip())

    def _build_auth_headers(self) -> Dict[str, str]:
        """Construct request headers with Bhashini authentication tokens."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if settings.bhashini_api_key:
            api_key = settings.bhashini_api_key.strip()
            headers["Authorization"] = api_key
            headers["ulcaApiKey"] = api_key
        if settings.bhashini_user_id:
            user_id = settings.bhashini_user_id.strip()
            headers["userID"] = user_id
            headers["User-ID"] = user_id
        return headers

    async def synthesize_speech(self, text: str, language: str = "en") -> Optional[str]:
        """
        Synthesize text into speech using Bhashini TTS pipeline.

        Args:
            text: Text script or bulletin to synthesize into speech.
            language: Target language name or code ('en', 'hi', 'or').

        Returns:
            Base64-encoded audio string (WAV/MP3), or None if Bhashini is unconfigured or unavailable.
        """
        clean_text = (text or "").strip()
        if not clean_text:
            logger.warning("Bhashini TTS requested with empty text payload.")
            return None

        if not self.is_configured():
            logger.info("Bhashini API key not configured; returning fallback signal for client-side TTS.")
            return None

        target_lang = self.normalize_language(language)

        payload: Dict[str, Any] = {
            "pipelineTasks": [
                {
                    "taskType": "tts",
                    "config": {
                        "language": {
                            "sourceLanguage": target_lang
                        },
                        "gender": "female",
                        "samplingRate": 22050
                    }
                }
            ],
            "inputData": {
                "input": [
                    {
                        "source": clean_text
                    }
                ]
            }
        }

        if settings.bhashini_pipeline_id and settings.bhashini_pipeline_id.strip():
            payload["pipelineTasks"][0]["config"]["pipelineId"] = settings.bhashini_pipeline_id.strip()

        try:
            client = await self._get_client()
            headers = self._build_auth_headers()
            
            logger.info(f"Dispatching Bhashini TTS synthesis request (lang={target_lang}, length={len(clean_text)})")
            response = await client.post(
                settings.bhashini_inference_url,
                json=payload,
                headers=headers
            )

            if response.status_code != 200:
                logger.warning(
                    f"Bhashini TTS returned non-200 status {response.status_code}: {response.text[:200]}"
                )
                return None

            data = response.json()
            return self._extract_audio_base64(data)

        except httpx.TimeoutException as err:
            logger.warning(f"Bhashini TTS request timed out after {settings.bhashini_timeout_seconds}s: {err}")
            return None
        except httpx.RequestError as err:
            logger.warning(f"Bhashini TTS network request error: {err}")
            return None
        except Exception as err:
            logger.error(f"Unexpected error in Bhashini TTS synthesis: {err}", exc_info=True)
            return None

    async def transcribe_audio(self, audio_base64: str, language: str = "en") -> Optional[str]:
        """
        Transcribe base64-encoded audio into text using Bhashini ASR pipeline.

        Args:
            audio_base64: Raw or data-URI base64-encoded audio bytes (WAV/WebM).
            language: Expected spoken language name or code ('en', 'hi', 'or').

        Returns:
            Transcribed string text, or None if Bhashini is unconfigured or unfulfilled.
        """
        if not audio_base64 or not audio_base64.strip():
            logger.warning("Bhashini ASR requested with empty audio payload.")
            return None

        if not self.is_configured():
            logger.info("Bhashini API key not configured; returning fallback signal for client-side ASR.")
            return None

        # Clean data URI prefix if present (e.g. data:audio/wav;base64,...)
        clean_audio = audio_base64.strip()
        if "," in clean_audio:
            clean_audio = clean_audio.split(",", 1)[1].strip()

        target_lang = self.normalize_language(language)

        payload: Dict[str, Any] = {
            "pipelineTasks": [
                {
                    "taskType": "asr",
                    "config": {
                        "language": {
                            "sourceLanguage": target_lang
                        },
                        "audioFormat": "wav",
                        "samplingRate": 16000
                    }
                }
            ],
            "inputData": {
                "audio": [
                    {
                        "audioContent": clean_audio
                    }
                ]
            }
        }

        if settings.bhashini_pipeline_id and settings.bhashini_pipeline_id.strip():
            payload["pipelineTasks"][0]["config"]["pipelineId"] = settings.bhashini_pipeline_id.strip()

        try:
            client = await self._get_client()
            headers = self._build_auth_headers()

            logger.info(f"Dispatching Bhashini ASR transcription request (lang={target_lang})")
            response = await client.post(
                settings.bhashini_inference_url,
                json=payload,
                headers=headers
            )

            if response.status_code != 200:
                logger.warning(
                    f"Bhashini ASR returned non-200 status {response.status_code}: {response.text[:200]}"
                )
                return None

            data = response.json()
            return self._extract_transcribed_text(data)

        except httpx.TimeoutException as err:
            logger.warning(f"Bhashini ASR request timed out after {settings.bhashini_timeout_seconds}s: {err}")
            return None
        except httpx.RequestError as err:
            logger.warning(f"Bhashini ASR network request error: {err}")
            return None
        except Exception as err:
            logger.error(f"Unexpected error in Bhashini ASR transcription: {err}", exc_info=True)
            return None

    def _extract_audio_base64(self, data: Dict[str, Any]) -> Optional[str]:
        """Parse Bhashini Dhruva TTS response schemas robustly."""
        try:
            # Standard Pipeline Response Schema
            pipeline_responses = data.get("pipelineResponse", [])
            for task in pipeline_responses:
                if task.get("taskType") == "tts" or "audio" in task:
                    audios = task.get("audio", [])
                    if audios and isinstance(audios, list):
                        first_audio = audios[0]
                        if isinstance(first_audio, dict) and "audioContent" in first_audio:
                            return first_audio["audioContent"]

            # Direct audio array schema
            if "audio" in data and isinstance(data["audio"], list) and data["audio"]:
                first_audio = data["audio"][0]
                if isinstance(first_audio, dict) and "audioContent" in first_audio:
                    return first_audio["audioContent"]

            # Root level audioContent schema
            if "audioContent" in data and isinstance(data["audioContent"], str):
                return data["audioContent"]

            logger.warning(f"Could not locate audioContent in Bhashini TTS response: {list(data.keys())}")
            return None
        except Exception as err:
            logger.error(f"Error extracting audioContent from Bhashini response: {err}")
            return None

    def _extract_transcribed_text(self, data: Dict[str, Any]) -> Optional[str]:
        """Parse Bhashini Dhruva ASR response schemas robustly."""
        try:
            # Standard Pipeline Response Schema
            pipeline_responses = data.get("pipelineResponse", [])
            for task in pipeline_responses:
                if task.get("taskType") == "asr" or "output" in task:
                    outputs = task.get("output", [])
                    if outputs and isinstance(outputs, list):
                        first_output = outputs[0]
                        if isinstance(first_output, dict):
                            # Usually source has the recognized text
                            text = first_output.get("source") or first_output.get("target")
                            if text:
                                return text.strip()

            # Direct output array schema
            if "output" in data and isinstance(data["output"], list) and data["output"]:
                first_output = data["output"][0]
                if isinstance(first_output, dict):
                    text = first_output.get("source") or first_output.get("target")
                    if text:
                        return text.strip()

            # Root level text schema
            if "text" in data and isinstance(data["text"], str):
                return data["text"].strip()

            logger.warning(f"Could not locate transcribed text in Bhashini ASR response: {list(data.keys())}")
            return None
        except Exception as err:
            logger.error(f"Error extracting transcribed text from Bhashini response: {err}")
            return None


# Singleton Service Instance
bhashini_service = BhashiniService()
