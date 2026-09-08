"""
WeatherGPT - SIH26068 (Ministry of Earth Sciences)
Meteorological Decision-Support & Disaster Early-Warning Web Application

Modular FastAPI Gateway integrating dynamic geocoding, asynchronous numerical telemetry ingestion,
deterministic IMD/NDMA disaster matrix calculations, and multilingual bulletin synthesis.
"""

import os
import datetime
import logging
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.services.weather_service import weather_service, LocationNotFoundError
from app.services.hazard_engine import evaluate_hazard_matrix, compute_agro_advisory, compute_marine_advisory
from app.services.synthesizer import synthesize_bulletin
from app.services.bhashini_service import bhashini_service

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("WeatherGPT.Main")

# FastAPI App Instance
app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class WeatherQueryPayload(BaseModel):
    """Schema for meteorological bulletin query."""
    location: Optional[str] = Field(None, description="Target Indian district, city, sub-division, or pincode (e.g., 'Bhubaneswar', 'Puri', 'Delhi', '751024')")
    city: Optional[str] = Field(None, description="Alternative key for backward compatibility")
    language: str = Field(default="en", description="Advisory language: 'en' (English), 'hi' (Hindi), 'or' (Odia)")
    role: Optional[str] = Field(default="general", description="User persona: 'general', 'farmer', 'fisherman'")


class TTSRequestPayload(BaseModel):
    """Schema for Bhashini text-to-speech synthesis request."""
    text: str = Field(..., min_length=1, description="Advisory bulletin text or narrative script to synthesize")
    language: str = Field(default="en", description="Language code or name ('en', 'hi', 'or', 'English', 'Hindi', 'Odia')")


class ASRRequestPayload(BaseModel):
    """Schema for Bhashini automated speech recognition audio transcription."""
    audio: str = Field(..., min_length=1, description="Base64-encoded audio waveform string (WAV or WebM)")
    language: Optional[str] = Field(default="en", description="Target spoken Indic language ('en', 'hi', 'or')")


@app.post("/api/voice/tts")
async def synthesize_speech_endpoint(payload: TTSRequestPayload):
    """
    Bhashini Multilingual Text-to-Speech (TTS) Endpoint:
    Synthesizes meteorological advisory scripts into Indic speech audio via Government of India Bhashini Dhruva Pipeline.
    Gracefully signals client-side fallback if keys are unconfigured or remote service is unreachable.
    """
    clean_text = payload.text.strip()
    if not clean_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Speech synthesis text cannot be empty."
        )

    target_lang = bhashini_service.normalize_language(payload.language)
    audio_base64 = await bhashini_service.synthesize_speech(clean_text, target_lang)

    if audio_base64:
        return {
            "status": "success",
            "audio_content": audio_base64,
            "format": "audio/wav",
            "source": "bhashini",
            "language": target_lang,
            "fallback": False
        }

    return {
        "status": "fallback",
        "fallback": True,
        "audio_content": None,
        "source": "web_speech_fallback",
        "language": target_lang,
        "message": "Bhashini TTS unavailable or unconfigured; client fallback to Web Speech API enabled."
    }


@app.post("/api/voice/asr")
async def transcribe_speech_endpoint(payload: ASRRequestPayload):
    """
    Bhashini Indic Automated Speech Recognition (ASR) Endpoint:
    Transcribes user spoken voice queries into district / location search strings.
    """
    clean_audio = payload.audio.strip()
    if not clean_audio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio payload cannot be empty."
        )

    target_lang = bhashini_service.normalize_language(payload.language)
    transcribed_text = await bhashini_service.transcribe_audio(clean_audio, target_lang)

    if transcribed_text:
        return {
            "status": "success",
            "text": transcribed_text,
            "source": "bhashini",
            "language": target_lang,
            "fallback": False
        }

    return {
        "status": "fallback",
        "fallback": True,
        "text": "",
        "source": "client_asr_fallback",
        "language": target_lang,
        "message": "Bhashini ASR unavailable or unconfigured; client-side speech recognition fallback enabled."
    }


@app.post("/api/query")
async def process_meteorological_query(payload: WeatherQueryPayload):
    """
    Core Decision-Support Endpoint:
    1. Dynamically geocodes target Indian location via Open-Meteo API.
    2. Ingests live telemetry (temperature, wind, gusts, precipitation, humidity, WMO code) with TTL caching.
    3. Runs deterministic IMD/NDMA 4-tier alert matrix.
    4. Computes Agro-meteorological (Agromet) and Marine/Fishermen directives.
    5. Synthesizes official bulletin and speech-optimized TTS script in English, Hindi, or Odia.
    """
    target_query = (payload.location or payload.city or "").strip()
    if not target_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Location query is required. Please specify an Indian district, city, or pincode."
        )

    # 1. Asynchronous Dynamic Geocoding
    try:
        location_data = await weather_service.resolve_coordinates(target_query)
    except LocationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except Exception as err:
        logger.error(f"Geocoding exception for '{target_query}': {err}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Geocoding failure: {str(err)}")

    lat = location_data["latitude"]
    lon = location_data["longitude"]

    # 2. Asynchronous Meteorological Telemetry Ingestion
    try:
        telemetry = await weather_service.get_live_metrics(lat, lon)
    except Exception as err:
        logger.error(f"Telemetry ingestion exception for ({lat}, {lon}): {err}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Live meteorological telemetry error: {str(err)}")

    # 3. Deterministic IMD / NDMA 4-Tier Disaster Warning Matrix
    hazard_info = evaluate_hazard_matrix(
        wind_speed=telemetry["wind_speed_kmh"],
        wind_gusts=telemetry["wind_gusts_kmh"],
        precipitation=telemetry["precipitation_mm"],
        daily_rain=telemetry["daily_rain_total_mm"],
        weather_code=telemetry["weather_code"],
        temp=telemetry["temperature_c"]
    )

    # 4. Agro-Meteorological Advisories
    agro_info = compute_agro_advisory(
        wind_speed=telemetry["wind_speed_kmh"],
        precipitation=telemetry["precipitation_mm"],
        humidity=telemetry["humidity_percent"],
        temp=telemetry["temperature_c"],
        weather_code=telemetry["weather_code"]
    )

    # 5. Coastal & Marine Fishermen Directives
    marine_info = compute_marine_advisory(
        wind_speed=telemetry["wind_speed_kmh"],
        wind_gusts=telemetry["wind_gusts_kmh"],
        precipitation=telemetry["precipitation_mm"],
        is_coastal=location_data["is_coastal"]
    )

    # 6. Multilingual Ground-Truth Bulletin Synthesis
    multilingual = synthesize_bulletin(
        location_data=location_data,
        metrics=telemetry,
        hazard=hazard_info,
        agro=agro_info,
        marine=marine_info,
        language=payload.language
    )

    # 7. Assemble Production Response
    response_payload = {
        "status": "success",
        "city": location_data["name"],
        "state": location_data["state"],
        "country": location_data["country"],
        "coordinates": {
            "latitude": location_data["latitude"],
            "longitude": location_data["longitude"]
        },
        "elevation": location_data["elevation"],
        "is_coastal": location_data["is_coastal"],
        "coastal_proximity": location_data["coastal_proximity"],
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "telemetry": {
            "temperature_c": telemetry["temperature_c"],
            "apparent_temperature_c": telemetry["apparent_temperature_c"],
            "humidity_percent": telemetry["humidity_percent"],
            "wind_speed_kmh": telemetry["wind_speed_kmh"],
            "wind_gusts_kmh": telemetry["wind_gusts_kmh"],
            "wind_direction_deg": telemetry["wind_direction_deg"],
            "cloud_cover_percent": telemetry["cloud_cover_percent"],
            "precipitation_mm": telemetry["precipitation_mm"],
            "daily_rain_total_mm": telemetry["daily_rain_total_mm"],
            "daily_wind_max_kmh": telemetry["daily_wind_max_kmh"],
            "weather_code": telemetry["weather_code"],
            "condition": multilingual["condition_text"]
        },
        "alert": hazard_info,
        "agro_advisory": agro_info,
        "coastal_advisory": marine_info,
        "multilingual": multilingual,
        "source": "Ministry of Earth Sciences (MoES) / IMD Deterministic Decision Engine"
    }

    return response_payload


@app.get("/api/health")
async def health_check():
    """Diagnostic health check for the meteorological microservice."""
    return {
        "status": "online",
        "service": settings.app_name,
        "version": settings.app_version,
        "sih_track": settings.sih_track,
        "endpoints": {
            "geocoding": settings.geocoding_api_url,
            "telemetry": settings.weather_api_url,
            "bhashini_pipeline": settings.bhashini_inference_url
        },
        "bhashini": {
            "configured": bhashini_service.is_configured(),
            "pipeline_id": bool(settings.bhashini_pipeline_id),
            "supported_voice_languages": ["en", "hi", "or"]
        },
        "supported_languages": ["en", "hi", "or"],
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }


# Static Files Mount
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    """Serve the single-page official administrative portal."""
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": f"{settings.app_name} is running. Place index.html in the static/ directory."}
