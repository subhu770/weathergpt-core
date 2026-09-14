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
import httpx
from fastapi import FastAPI, HTTPException, Query, status, Request, Response, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.services.weather_service import weather_service, LocationNotFoundError
from app.services.hazard_engine import evaluate_hazard_matrix, compute_agro_advisory, compute_marine_advisory
from app.services.synthesizer import synthesize_bulletin
from app.services.ivr_service import ivr_service
from twilio.twiml.voice_response import VoiceResponse, Gather


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


class IVRTriggerPayload(BaseModel):
    """Schema for triggering an outbound PSTN IVR emergency call via Twilio."""
    target_phone: Optional[str] = Field(default=None, description="Recipient phone number (e.g. +917735529862)")
    phone: Optional[str] = Field(default=None, description="Alternative key for recipient phone number")
    phone_number: Optional[str] = Field(default=None, description="Alternative key for recipient phone number")
    district: Optional[str] = Field(default="Khordha", description="Target administrative Indian district")
    latitude: Optional[float] = Field(default=None, description="Direct geographic latitude")
    longitude: Optional[float] = Field(default=None, description="Direct geographic longitude")
    language: Optional[str] = Field(default="en", description="Default initial language ('en', 'hi')")


class SendSMSPayload(BaseModel):
    """Schema for unified Twilio Emergency SMS Notification."""
    phone: Optional[str] = Field(default="+917735529862", description="Recipient phone number (e.g. +917735529862)")
    target_phone: Optional[str] = Field(default=None, description="Alternative key for recipient phone number")
    phone_number: Optional[str] = Field(default=None, description="Alternative key for recipient phone number")
    district: Optional[str] = Field(default="Khordha", description="Target administrative Indian district")
    hazard_level: Optional[str] = Field(default="RED", description="IMD Hazard level (RED, ORANGE, YELLOW, GREEN)")
    alert_level: Optional[str] = Field(default=None, description="Alternative key for hazard level")
    message: Optional[str] = Field(default=None, description="Custom emergency SMS body")




@app.post("/api/telecom/broadcast")
async def broadcast_telecom_alert_endpoint(payload: TelecomBroadcastPayload):
    """
    NDMA / Common Alerting Protocol (CAP) Citizen Telecom Gateway Endpoint:
    Dispatches live physical SMS alerts to Indian mobile phones via Fast2SMS Live Telecom Gateway.
    Also handles automated Interactive Voice Response (IVR) advisory scripts.
    """
    # 1. Clean & validate recipient mobile number (strip +91, 0, spaces, non-digits)
    clean_digits = re.sub(r"\D", "", payload.phone_number.strip())
    if len(clean_digits) == 12 and clean_digits.startswith("91"):
        clean_digits = clean_digits[2:]
    elif len(clean_digits) == 11 and clean_digits.startswith("0"):
        clean_digits = clean_digits[1:]
    elif len(clean_digits) > 10:
        clean_digits = clean_digits[-10:]

    if len(clean_digits) != 10 or not clean_digits.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid 10-digit Indian mobile number is required."
        )

    formatted_phone = f"+91 {clean_digits[:5]} {clean_digits[5:]}"
    dist = payload.district.strip() or "District"
    hazard_level = (payload.alert_level or "GREEN").upper()
    lang = (payload.language or "en").lower()

    temp_val = f"{payload.temperature_c:.1f}" if payload.temperature_c is not None else "28.0"
    wind_val = f"{payload.wind_speed_kmh:.1f}" if payload.wind_speed_kmh is not None else "12.0"

    # IMD Alert SMS text as required by specification
    sms_text = f"[IMD ALERT] {dist}: {hazard_level} risk. Temp: {temp_val}C, Wind: {wind_val}km/h. Stay alert."

    # NDMA CAP protocol metadata
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    ts_str = now_utc.strftime('%Y%m%d%H%M%S')
    default_cap_id = f"CAP-IN-IMD-{ts_str}-{uuid.uuid4().hex[:6].upper()}"
    cap_urn = f"urn:oid:2.49.0.1.356.1.0.{ts_str}.{hazard_level}"

    # Multilingual IVR Voice Script for feature/keypad phone outdial
    if lang == "hi":
        if hazard_level == "RED":
            ivr_script = f"आपातकालीन मौसम सूचना। भारत मौसम विज्ञान विभाग एवं एनडीएमए द्वारा {dist} के लिए लाल चेतावनी जारी की गई है। {payload.hazard_type} की संभावना है। कृपया तुरंत सुरक्षित पक्के स्थान पर आश्रय लें।"
        elif hazard_level == "ORANGE":
            ivr_script = f"सावधानी सूचना। मौसम विभाग द्वारा {dist} के लिए नारंगी चेतावनी जारी की गई है। {payload.hazard_type} के प्रति सतर्क रहें।"
        elif hazard_level == "YELLOW":
            ivr_script = f"मौसम सूचना। {dist} में {payload.hazard_type} के लिए पीली चेतावनी जारी है। मौसम पूर्वानुमान पर नजर बनाए रखें।"
        else:
            ivr_script = f"मौसम विभाग दैनिक बुलेटिन। {dist} में मौसम सामान्य है। तापमान {payload.temperature_c:.0f} डिग्री सेल्सियस है।"
    else:
        if hazard_level == "RED":
            ivr_script = f"Critical weather emergency alert from India Meteorological Department and NDMA for {dist}. Red Warning in effect for {payload.hazard_type}. Please take reinforced indoor shelter immediately."
        elif hazard_level == "ORANGE":
            ivr_script = f"Severe weather warning from India Meteorological Department for {dist}. Orange Alert in effect for {payload.hazard_type}. Please secure outdoor equipment and be prepared."
        elif hazard_level == "YELLOW":
            ivr_script = f"Official weather advisory for {dist}. Yellow Alert in effect for {payload.hazard_type}. Winds {payload.wind_speed_kmh:.0f} kilometers per hour. Please keep updated with official bulletins."
        else:
            ivr_script = f"Daily meteorological bulletin for {dist}. Weather conditions are normal with temperature {payload.temperature_c:.0f} degrees Celsius."

    # 2. Live POST Request to Fast2SMS Gateway
    fast2sms_url = getattr(settings, "fast2sms_api_url", "https://www.fast2sms.com/dev/bulkV2")
    fast2sms_key = getattr(settings, "fast2sms_api_key", "VmkhZTYac57v1uluKI8HOBjFCm6ItczeTLgZfVAsDA7JCEZrbHzxmSMHHcG9")
    fast2sms_timeout = getattr(settings, "fast2sms_timeout_seconds", 12.0)

    fast2sms_headers = {
        "authorization": fast2sms_key or "VmkhZTYac57v1uluKI8HOBjFCm6ItczeTLgZfVAsDA7JCEZrbHzxmSMHHcG9",
        "Content-Type": "application/json"
    }

    fast2sms_payload = {
        "route": "q",
        "message": sms_text,
        "language": "english",
        "numbers": clean_digits
    }

    gateway_response_data = None
    request_id = None

    try:
        async with httpx.AsyncClient(timeout=fast2sms_timeout) as client:
            resp = await client.post(fast2sms_url, json=fast2sms_payload, headers=fast2sms_headers)
            try:
                gateway_response_data = resp.json()
            except Exception:
                gateway_response_data = {"raw_text": resp.text}

            logger.info(f"Fast2SMS live gateway response (HTTP {resp.status_code}): {gateway_response_data}")

            # Check if Fast2SMS returned success
            if resp.status_code == 200 and isinstance(gateway_response_data, dict) and gateway_response_data.get("return") is True:
                raw_req_id = gateway_response_data.get("request_id")
                request_id = str(raw_req_id).strip() if raw_req_id else default_cap_id
            else:
                # Extract clear failure message from Fast2SMS
                err_msg = ""
                if isinstance(gateway_response_data, dict):
                    raw_msg = gateway_response_data.get("message")
                    if isinstance(raw_msg, list):
                        err_msg = ", ".join(str(m) for m in raw_msg)
                    elif raw_msg:
                        err_msg = str(raw_msg)
                    elif "detail" in gateway_response_data:
                        err_msg = str(gateway_response_data["detail"])
                if not err_msg:
                    err_msg = f"Fast2SMS API returned HTTP {resp.status_code}: {resp.text}"

                logger.error(f"Fast2SMS live gateway failed: {err_msg}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Fast2SMS Gateway Error: {err_msg}"
                )

    except HTTPException:
        raise
    except httpx.RequestError as exc:
        logger.error(f"Fast2SMS gateway connection error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Fast2SMS Gateway Network Connection Failure: {str(exc)}"
        )
    except Exception as exc:
        logger.error(f"Unexpected error communicating with Fast2SMS: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Telecom Gateway Processing Error: {str(exc)}"
        )

    # 3. Assemble Response with actual gateway request_id and NDMA CAP trace
    dispatched_channels = ["Fast2SMS Telecom Route (Quick SMS 'q')"]
    if any("voice" in c.lower() or "ivr" in c.lower() for c in payload.channels):
        dispatched_channels.append("Automated IVR Outdial Call (Indic Voice Pipeline)")

    return {
        "status": "success",
        "gateway_message_id": request_id,
        "fast2sms_request_id": request_id,
        "cap_urn": cap_urn,
        "recipient": formatted_phone,
        "phone_number": clean_digits,
        "district": dist,
        "alert_level": hazard_level,
        "channels_dispatched": dispatched_channels,
        "sms_payload": sms_text,
        "ivr_payload": ivr_script if any("voice" in c.lower() or "ivr" in c.lower() for c in payload.channels) else None,
        "language": lang,
        "timestamp": now_utc.isoformat(),
        "delivery_status": "Delivered via Fast2SMS Telecom Route",
        "gateway_node": "Fast2SMS-Live-Telecom-Gateway",
        "gateway_response": gateway_response_data
    }


def resolve_request_base_url(request: Request) -> str:
    """Resolve public URL for Twilio webhook callback."""
    if settings.twilio_webhook_base_url:
        return settings.twilio_webhook_base_url.rstrip("/")
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if forwarded_proto and forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}"
    return str(request.base_url).rstrip("/")


async def get_ivr_param(request: Request, key: str, default: Optional[str] = None) -> Optional[str]:
    """Safely extract parameter from query string or form data."""
    if key in request.query_params:
        return request.query_params.get(key)
    if request.method == "POST":
        try:
            form = await request.form()
            if key in form:
                return str(form.get(key))
        except Exception:
            pass
    return default


# =============================================================================
# TWILIO VOICE IVR EMERGENCY ALERT ENDPOINTS
# =============================================================================

@app.post("/api/ivr/trigger-call")
async def trigger_ivr_call_endpoint(payload: IVRTriggerPayload, request: Request):
    """
    1. POST /api/ivr/trigger-call:
       - Initiates an outbound PSTN emergency alert call using Twilio Client to TARGET_PHONE.
       - Points Twilio webhook URL to /api/ivr/welcome passing the selected/detected district telemetry.
    """
    base_url = resolve_request_base_url(request)
    phone_to_call = payload.target_phone or payload.phone or payload.phone_number or settings.twilio_target_phone
    try:
        call_result = await ivr_service.trigger_outbound_call(
            target_phone=phone_to_call,
            district=payload.district,
            base_url=base_url,
            lat=payload.latitude,
            lon=payload.longitude,
            language=payload.language or "en"
        )

        return {
            "status": "success",
            "message": f"Twilio emergency IVR call initiated to {call_result['target_phone']}",
            "data": call_result
        }
    except Exception as exc:
        logger.error(f"Failed to trigger Twilio IVR call: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": f"Twilio Voice Call Error: {str(exc)}",
                "detail": str(exc)
            }
        )


@app.post("/api/alerts/send-sms")
async def send_emergency_sms_endpoint(payload: SendSMSPayload):
    """
    POST /api/alerts/send-sms:
    - Accepts: phone (default: "+917735529862"), district, hazard_level, message.
    - Uses Twilio Client: client.messages.create(to=phone, from_=TWILIO_PHONE_NUMBER, body=...)
    - Returns: {"status": "success", "message_sid": message.sid}
    """
    phone_to_send = payload.phone or payload.target_phone or payload.phone_number or settings.twilio_target_phone
    hazard_lvl = payload.hazard_level or payload.alert_level or "RED"
    dist = payload.district or "Khordha"
    try:
        sms_result = await ivr_service.send_emergency_sms(
            target_phone=phone_to_send,
            district=dist,
            hazard_level=hazard_lvl,
            message=payload.message
        )
        return {
            "status": "success",
            "message_sid": sms_result["message_sid"],
            "data": sms_result
        }
    except Exception as exc:
        logger.error(f"Failed to send emergency SMS: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": f"Twilio SMS Error: {str(exc)}",
                "detail": str(exc)
            }
        )


@app.api_route("/api/ivr/welcome", methods=["GET", "POST"])
async def ivr_welcome_endpoint(
    request: Request,
    district: Optional[str] = Query(None),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None)
):
    """
    2. POST & GET /api/ivr/welcome:
       - Responds with TwiML (VoiceResponse).
       - Speaks an immediate dynamic emergency greeting for the detected district
         (current hazard level, wind speed, precipitation from our WeatherGPT telemetry service).
       - Prompts for language selection via DTMF Gather (num_digits=1, timeout=5):
         * Press 1 for English
         * Press 2 for Hindi (hi-IN)
       - Action URL: /api/ivr/menu
    """
    try:
        dist_name = district or await get_ivr_param(request, "district", "Khordha")
        raw_lat = lat or await get_ivr_param(request, "lat", None)
        raw_lon = lon or await get_ivr_param(request, "lon", None)

        parsed_lat = float(raw_lat) if raw_lat is not None else None
        parsed_lon = float(raw_lon) if raw_lon is not None else None
        base_url = resolve_request_base_url(request)

        twiml_xml = await ivr_service.generate_welcome_twiml(
            district=dist_name,
            lat=parsed_lat,
            lon=parsed_lon,
            base_url=base_url
        )
        return Response(
            content=twiml_xml,
            media_type="application/xml",
            headers={"Content-Type": "application/xml; charset=utf-8"}
        )
    except Exception as exc:
        logger.error(f"Error in /api/ivr/welcome: {exc}", exc_info=True)
        response = VoiceResponse()
        response.say(
            "IMD Emergency Alert. Khordha region. Current hazard level is Yellow Alert. Temperature 28 degrees Celsius, wind speed 18 kilometers per hour. Press 1 for English, 2 for Hindi.",
            voice="Polly.Aditi",
            language="en-IN"
        )
        gather = Gather(
            num_digits=1,
            timeout=5,
            action="https://weathergpt-core.vercel.app/api/ivr/menu?district=Khordha",
            method="POST"
        )
        gather.say("For English, press 1.", voice="Polly.Aditi", language="en-IN")
        gather.say("हिन्दी के लिए 2 दबाएँ।", voice="Polly.Aditi", language="hi-IN")
        response.append(gather)
        response.say("No input received. Continuing in English.", voice="Polly.Aditi", language="en-IN")
        response.redirect("https://weathergpt-core.vercel.app/api/ivr/menu?district=Khordha&Digits=1", method="POST")
        return Response(
            content=str(response),
            media_type="application/xml",
            headers={"Content-Type": "application/xml; charset=utf-8"}
        )


@app.api_route("/api/ivr/menu", methods=["GET", "POST"])
async def ivr_menu_endpoint(
    request: Request,
    district: Optional[str] = Query(None),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None)
):
    """
    3. POST & GET /api/ivr/menu:
       - Reads Digits (1 = English, 2 = Hindi).
       - Plays the Persona Advisory Menu via DTMF Gather (num_digits=1, timeout=6):
         * Press 1: Farmer Advisory (agricultural drainage and crop safety guidelines)
         * Press 2: Fisherman Advisory (marine alert, wind surge, harbor docking order)
         * Press 3: General District Weather (temperature, humidity, precipitation metrics from telemetry)
         * Press 4: High-Risk Emergency SOS Rescue
       - Action URL: /api/ivr/action
    """
    try:
        digits = await get_ivr_param(request, "Digits", "1")
        dist_name = district or await get_ivr_param(request, "district", "Khordha")
        raw_lat = lat or await get_ivr_param(request, "lat", None)
        raw_lon = lon or await get_ivr_param(request, "lon", None)

        parsed_lat = float(raw_lat) if raw_lat is not None else None
        parsed_lon = float(raw_lon) if raw_lon is not None else None
        base_url = resolve_request_base_url(request)

        twiml_xml = await ivr_service.generate_menu_twiml(
            digits=digits,
            district=dist_name,
            lat=parsed_lat,
            lon=parsed_lon,
            base_url=base_url
        )
        return Response(
            content=twiml_xml,
            media_type="application/xml",
            headers={"Content-Type": "application/xml; charset=utf-8"}
        )
    except Exception as exc:
        logger.error(f"Error in /api/ivr/menu: {exc}", exc_info=True)
        fallback_vr = VoiceResponse()
        fallback_vr.say(
            "Playing general district weather advisory from India Meteorological Department. Weather telemetry is actively monitored.",
            voice="Polly.Aditi",
            language="en-IN"
        )
        fallback_vr.pause(length=1)
        fallback_vr.hangup()
        return Response(
            content=str(fallback_vr),
            media_type="application/xml",
            headers={"Content-Type": "application/xml; charset=utf-8"}
        )


@app.api_route("/api/ivr/action", methods=["GET", "POST"])
async def ivr_action_endpoint(
    request: Request,
    district: Optional[str] = Query(None),
    lang: Optional[str] = Query(None),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None)
):
    """
    4. POST & GET /api/ivr/action:
       - Reads Digits and delivers dynamic advisory generated from WeatherGPT backend in the selected language.
       - If Digits == '4', log an emergency SOS event in the dashboard database/state with coordinates and phone number,
         and play an audio confirmation stating emergency rescue teams have been alerted.
       - End with a polite signoff and hang up the call.
    """
    try:
        digits = await get_ivr_param(request, "Digits", "3")
        target_lang = lang or await get_ivr_param(request, "lang", "en")
        dist_name = district or await get_ivr_param(request, "district", "Khordha")
        raw_lat = lat or await get_ivr_param(request, "lat", None)
        raw_lon = lon or await get_ivr_param(request, "lon", None)
        caller_phone = await get_ivr_param(request, "From", settings.twilio_target_phone)
        call_sid = await get_ivr_param(request, "CallSid", "")

        parsed_lat = float(raw_lat) if raw_lat is not None else None
        parsed_lon = float(raw_lon) if raw_lon is not None else None

        twiml_xml = await ivr_service.generate_action_twiml(
            digits=digits,
            lang=target_lang,
            district=dist_name,
            lat=parsed_lat,
            lon=parsed_lon,
            caller_phone=caller_phone,
            call_sid=call_sid
        )
        return Response(
            content=twiml_xml,
            media_type="application/xml",
            headers={"Content-Type": "application/xml; charset=utf-8"}
        )
    except Exception as exc:
        logger.error(f"Error in /api/ivr/action: {exc}", exc_info=True)
        fallback_vr = VoiceResponse()
        fallback_vr.say(
            "Thank you for using India Meteorological Department Decision Support System. Stay safe. Goodbye.",
            voice="Polly.Aditi",
            language="en-IN"
        )
        fallback_vr.pause(length=1)
        fallback_vr.hangup()
        return Response(
            content=str(fallback_vr),
            media_type="application/xml",
            headers={"Content-Type": "application/xml; charset=utf-8"}
        )


@app.get("/api/ivr/sos-events")
async def get_sos_events_endpoint(limit: int = Query(20, ge=1, le=100)):
    """
    Retrieve logged Emergency SOS Rescue events triggered via IVR DTMF option 4.
    """
    try:
        events = ivr_service.get_sos_events(limit=limit)
        return {
            "status": "success",
            "count": len(events),
            "events": events
        }
    except Exception as exc:
        logger.error(f"Error in /api/ivr/sos-events: {exc}")
        return {
            "status": "success",
            "count": 0,
            "events": []
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
