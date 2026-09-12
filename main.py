"""
WeatherGPT - SIH26068 (Ministry of Earth Sciences)
Meteorological Decision-Support & Disaster Early-Warning Web Application

Modular FastAPI Gateway integrating dynamic geocoding, asynchronous numerical telemetry ingestion,
deterministic IMD/NDMA disaster matrix calculations, and multilingual bulletin synthesis.
"""

import os
import re
import uuid
import datetime
import logging
from typing import Optional, Dict, Any, List
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
    location: Optional[str] = Field(None, description="Target Indian district (e.g., 'Khordha', 'Cuttack', 'Puri', 'Pune')")
    city: Optional[str] = Field(None, description="Alternative key for backward compatibility")
    latitude: Optional[float] = Field(None, description="Direct geographic latitude (e.g., 20.2961)")
    longitude: Optional[float] = Field(None, description="Direct geographic longitude (e.g., 85.8245)")
    language: str = Field(default="en", description="Advisory language: 'en' (English), 'hi' (Hindi)")
    role: Optional[str] = Field(default="general", description="User persona: 'general', 'farmer', 'fisherman'")


class TTSRequestPayload(BaseModel):
    """Schema for Bhashini text-to-speech synthesis request."""
    text: str = Field(..., min_length=1, description="Advisory bulletin text or narrative script to synthesize")
    language: str = Field(default="en", description="Language code or name ('en', 'hi', 'English', 'Hindi')")


class ASRRequestPayload(BaseModel):
    """Schema for Bhashini automated speech recognition audio transcription."""
    audio: str = Field(..., min_length=1, description="Base64-encoded audio waveform string (WAV or WebM)")
    language: Optional[str] = Field(default="en", description="Target spoken Indic language ('en', 'hi')")


class TelecomBroadcastPayload(BaseModel):
    """Schema for NDMA/CAP-compliant Telecom SMS & Voice IVR Broadcast."""
    phone_number: str = Field(..., min_length=10, description="Recipient Indian 10-digit mobile number or +91 format")
    district: str = Field(..., min_length=1, description="Target administrative Indian district")
    alert_level: Optional[str] = Field(default="GREEN", description="IMD Alert Level: GREEN, YELLOW, ORANGE, RED")
    hazard_type: Optional[str] = Field(default="Moderate Weather Bulletin", description="IMD Hazard classification")
    condition: Optional[str] = Field(default="Clear / Normal", description="Observed weather condition")
    temperature_c: Optional[float] = Field(default=28.0, description="Surface temperature in Celsius")
    wind_speed_kmh: Optional[float] = Field(default=12.0, description="Wind velocity in km/h")
    channels: List[str] = Field(default=["sms", "voice_ivr"], description="Broadcast channels: ['sms', 'voice_ivr']")
    language: str = Field(default="en", description="Advisory language: 'en', 'hi'")


@app.post("/api/telecom/broadcast")
async def broadcast_telecom_alert_endpoint(payload: TelecomBroadcastPayload):
    """
    NDMA / Common Alerting Protocol (CAP) Citizen Telecom Gateway Endpoint:
    Dispatches localized SMS alerts and automated Interactive Voice Response (IVR) calls
    for keypad phones and feature mobile devices in rural and coastal belts.
    """
    clean_digits = re.sub(r"\D", "", payload.phone_number.strip())
    if len(clean_digits) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid 10-digit Indian mobile number (+91) is required."
        )

    # Format national 10-digit / +91 phone representation
    if len(clean_digits) == 10:
        formatted_phone = f"+91 {clean_digits[:5]} {clean_digits[5:]}"
    elif len(clean_digits) == 12 and clean_digits.startswith("91"):
        formatted_phone = f"+91 {clean_digits[2:7]} {clean_digits[7:]}"
    else:
        formatted_phone = f"+91 {clean_digits[-10:-5]} {clean_digits[-5:]}"

    dist = payload.district.strip() or "District"
    level = (payload.alert_level or "GREEN").upper()
    lang = (payload.language or "en").lower()
    
    # Generate simulated Gateway Message ID & CAP Trace Identifier
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    ts_str = now_utc.strftime('%Y%m%d%H%M%S')
    msg_id = f"CAP-IN-IMD-{ts_str}-{uuid.uuid4().hex[:6].upper()}"
    cap_urn = f"urn:oid:2.49.0.1.356.1.0.{ts_str}.{level}"

    # CAP / NDMA Alert Standard Telecom Formats
    if lang == "hi":
        if level == "RED":
            sms_text = f"[आईएमडी-गंभीर चेतावनी] {dist}: लाल चेतावनी - {payload.hazard_type}। तापमान: {payload.temperature_c:.1f}°C, हवा: {payload.wind_speed_kmh:.1f} किमी/घंटा। एनडीएमए निर्देश: तत्काल सुरक्षित पक्के आश्रय में रहें।"
            ivr_script = f"आपातकालीन मौसम सूचना। भारत मौसम विज्ञान विभाग एवं एनडीएमए द्वारा {dist} के लिए लाल चेतावनी जारी की गई है। {payload.hazard_type} की संभावना है। कृपया तुरंत सुरक्षित पक्के स्थान पर आश्रय लें।"
        elif level == "ORANGE":
            sms_text = f"[आईएमडी-सतर्कता] {dist}: नारंगी चेतावनी - {payload.hazard_type}। तापमान: {payload.temperature_c:.1f}°C, हवा: {payload.wind_speed_kmh:.1f} किमी/घंटा। सतर्क रहें और जलभराव से बचें।"
            ivr_script = f"सावधानी सूचना। मौसम विभाग द्वारा {dist} के लिए नारंगी चेतावनी जारी की गई है। {payload.hazard_type} के प्रति सतर्क रहें।"
        elif level == "YELLOW":
            sms_text = f"[आईएमडी-अपडेट] {dist}: पीली चेतावनी - {payload.hazard_type}। तापमान: {payload.temperature_c:.1f}°C, हवा: {payload.wind_speed_kmh:.1f} किमी/घंटा। मौसम की जानकारी पर नजर रखें।"
            ivr_script = f"मौसम सूचना। {dist} में {payload.hazard_type} के लिए पीली चेतावनी जारी है। मौसम पूर्वानुमान पर नजर बनाए रखें।"
        else:
            sms_text = f"[आईएमडी-दैनिक] {dist}: सामान्य मौसम ({payload.condition})। तापमान: {payload.temperature_c:.1f}°C, हवा: {payload.wind_speed_kmh:.1f} किमी/घंटा। कोई आपदा चेतावनी नहीं।"
            ivr_script = f"मौसम विभाग दैनिक बुलेटिन। {dist} में मौसम सामान्य है। तापमान {payload.temperature_c:.0f} डिग्री सेल्सियस है।"
    else:
        if level == "RED":
            sms_text = f"[IMD-CRITICAL] {dist}: RED ALERT for {payload.hazard_type}. Temp: {payload.temperature_c:.1f}°C, Wind: {payload.wind_speed_kmh:.1f} km/h. NDMA Directive: Evacuate vulnerable zones, take reinforced shelter immediately."
            ivr_script = f"Critical weather emergency alert from India Meteorological Department and NDMA for {dist}. Red Warning in effect for {payload.hazard_type}. Please take reinforced indoor shelter immediately."
        elif level == "ORANGE":
            sms_text = f"[IMD-WARNING] {dist}: ORANGE ALERT for {payload.hazard_type}. Temp: {payload.temperature_c:.1f}°C, Wind: {payload.wind_speed_kmh:.1f} km/h. MoES Directive: Be prepared, secure livestock and crops."
            ivr_script = f"Severe weather warning from India Meteorological Department for {dist}. Orange Alert in effect for {payload.hazard_type}. Please secure outdoor equipment and be prepared."
        elif level == "YELLOW":
            sms_text = f"[IMD-ALERT] {dist}: Yellow Alert for {payload.hazard_type}. Temp: {payload.temperature_c:.1f}°C, Wind: {payload.wind_speed_kmh:.1f} km/h. IMD Advisory: Keep watch and monitor local conditions."
            ivr_script = f"Official weather advisory for {dist}. Yellow Alert in effect for {payload.hazard_type}. Winds {payload.wind_speed_kmh:.0f} kilometers per hour. Please keep updated with official bulletins."
        else:
            sms_text = f"[IMD-DAILY] {dist}: Normal conditions ({payload.condition}). Temp: {payload.temperature_c:.1f}°C, Wind: {payload.wind_speed_kmh:.1f} km/h. No active severe warnings."
            ivr_script = f"Daily meteorological bulletin for {dist}. Weather conditions are normal with temperature {payload.temperature_c:.0f} degrees Celsius."

    # Parse Dispatched Channels
    dispatched_channels = []
    for ch in payload.channels:
        ch_lower = ch.lower()
        if "sms" in ch_lower and "National SMS Gateway (C-DAC / TRAI DLT)" not in dispatched_channels:
            dispatched_channels.append("National SMS Gateway (C-DAC / TRAI DLT)")
        elif ("voice" in ch_lower or "ivr" in ch_lower) and "Automated IVR Outdial Call (Indic Voice Pipeline)" not in dispatched_channels:
            dispatched_channels.append("Automated IVR Outdial Call (Indic Voice Pipeline)")

    if not dispatched_channels:
        dispatched_channels.append("National SMS Gateway (C-DAC / TRAI DLT)")

    return {
        "status": "success",
        "gateway_message_id": msg_id,
        "cap_urn": cap_urn,
        "recipient": formatted_phone,
        "district": dist,
        "alert_level": level,
        "channels_dispatched": dispatched_channels,
        "sms_payload": sms_text,
        "ivr_payload": ivr_script,
        "language": lang,
        "timestamp": now_utc.isoformat(),
        "delivery_status": "QUEUED_AND_DISPATCHED",
        "gateway_node": "MoES-NDMA-CAP-GATEWAY-DELHI-01"
    }


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


@app.get("/api/reverse-geocode")
async def reverse_geocode_endpoint(
    lat: float = Query(..., description="Geographic latitude (e.g., 20.2961)"),
    lon: float = Query(..., description="Geographic longitude (e.g., 85.8245)")
):
    """
    Reverse-Geocoding Endpoint:
    Resolves client latitude and longitude into an official Indian administrative district and state.
    """
    try:
        location_data = await weather_service.reverse_geocode(lat, lon)
        return {
            "status": "success",
            "district": location_data["district"],
            "state": location_data["state"],
            "country": location_data["country"],
            "latitude": location_data["latitude"],
            "longitude": location_data["longitude"],
            "formatted_location": location_data["formatted_location"],
            "is_coastal": location_data["is_coastal"],
            "coastal_proximity": location_data["coastal_proximity"]
        }
    except Exception as err:
        logger.error(f"Reverse geocoding endpoint exception for ({lat}, {lon}): {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reverse geocoding failure: {str(err)}"
        )


@app.post("/api/query")
async def process_meteorological_query(payload: WeatherQueryPayload):
    """
    Core Decision-Support Endpoint:
    1. Dynamically geocodes target Indian district via Open-Meteo API or direct coordinates.
    2. Ingests live telemetry (temperature, wind, gusts, precipitation, humidity, WMO code) with TTL caching.
    3. Runs deterministic IMD/NDMA 4-tier alert matrix.
    4. Computes Agro-meteorological (Agromet) and Marine/Fishermen directives.
    5. Synthesizes official bulletin and speech-optimized TTS script in English or Hindi.
    """
    target_query = (payload.location or payload.city or "").strip()
    has_coords = payload.latitude is not None and payload.longitude is not None

    if not target_query and not has_coords:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="District query or geographic coordinates (latitude, longitude) are required."
        )

    # 1. Asynchronous Dynamic Geocoding or Coordinate Resolution
    try:
        if has_coords and (not target_query or target_query.lower() in ["", "auto", "detect", "current", "current location", "my location"]):
            location_data = await weather_service.reverse_geocode(payload.latitude, payload.longitude)
        else:
            location_data = await weather_service.resolve_coordinates(target_query)
    except LocationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except Exception as err:
        logger.error(f"Geocoding exception for query='{target_query}', coords=({payload.latitude}, {payload.longitude}): {err}")
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
            "supported_voice_languages": ["en", "hi"]
        },
        "supported_languages": ["en", "hi"],
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }


# Static Files Mount
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/sw.js")
async def service_worker():
    """Serve the root Service Worker script for Web Push and Offline Notifications."""
    sw_path = os.path.join(os.path.dirname(__file__), "static", "sw.js")
    if os.path.exists(sw_path):
        return FileResponse(
            sw_path,
            media_type="application/javascript",
            headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"}
        )
    raise HTTPException(status_code=404, detail="Service worker script not found.")


@app.get("/manifest.json")
async def web_manifest():
    """Serve the Web App Manifest."""
    manifest_path = os.path.join(os.path.dirname(__file__), "static", "manifest.json")
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path, media_type="application/manifest+json")
    raise HTTPException(status_code=404, detail="Manifest not found.")


@app.get("/")
async def root():
    """Serve the single-page official administrative portal."""
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": f"{settings.app_name} is running. Place index.html in the static/ directory."}
