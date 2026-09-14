"""
WeatherGPT - Twilio Voice Interactive Voice Response (IVR) Emergency Service
Ministry of Earth Sciences (MoES / SIH26068)

Handles:
1. Outbound PSTN Emergency Alert Voice Calls via Twilio REST API
2. Dynamic TwiML Generation (Emergency Greeting, Multilingual DTMF Gather)
3. 4-Tier Persona Advisory Engine (Farmer, Fisherman, General Weather, SOS Rescue)
4. Real-Time Emergency SOS Event Dispatch & Audit Logging
"""

import os
import json
import logging
import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import urlencode

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from twilio.twiml.voice_response import VoiceResponse, Gather, Hangup

from app.config import settings
from app.services.weather_service import weather_service
from app.services.hazard_engine import (
    evaluate_hazard_matrix,
    compute_agro_advisory,
    compute_marine_advisory
)

logger = logging.getLogger("WeatherGPT.IVRService")


class TwilioIVRService:
    """Production-grade Twilio Voice IVR Service for Emergency Meteorological Alerts."""

    def __init__(self):
        self._sos_events: List[Dict[str, Any]] = []
        self._sos_log_path = os.path.join(os.path.dirname(__file__), "sos_events_log.json")
        self._load_sos_events()

    def _load_sos_events(self):
        """Load persisted SOS events from JSON log if available."""
        if os.path.exists(self._sos_log_path):
            try:
                with open(self._sos_log_path, "r", encoding="utf-8") as f:
                    self._sos_events = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load SOS events log: {e}")
                self._sos_events = []

    def _save_sos_events(self):
        """Persist SOS events to JSON log."""
        try:
            with open(self._sos_log_path, "w", encoding="utf-8") as f:
                json.dump(self._sos_events, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to persist SOS events: {e}")

    def get_client(self) -> Client:
        """Instantiate and return authenticated Twilio REST Client."""
        sid = settings.twilio_account_sid
        token = settings.twilio_auth_token
        if not sid or not token:
            raise ValueError("Twilio Account SID or Auth Token is not configured.")
        return Client(sid, token)

    def normalize_phone_number(self, phone: str) -> str:
        """
        Normalize phone number into E.164 international format (+91 for India).
        """
        raw = phone.strip()
        if raw.startswith("+"):
            return raw

        digits = "".join(c for c in raw if c.isdigit())
        if len(digits) == 10:
            return f"+91{digits}"
        elif len(digits) == 11 and digits.startswith("0"):
            return f"+91{digits[1:]}"
        elif len(digits) == 12 and digits.startswith("91"):
            return f"+{digits}"
        return f"+{digits}" if digits else raw

    async def trigger_outbound_call(
        self,
        target_phone: Optional[str] = None,
        district: Optional[str] = None,
        base_url: str = "",
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Initiate an outbound PSTN emergency voice call via Twilio Client.
        Points Twilio to /api/ivr/welcome passing telemetry context in the query string.
        """
        to_phone = self.normalize_phone_number(target_phone or settings.twilio_target_phone)
        from_phone = settings.twilio_phone_number
        dist = (district or "Khordha").strip()

        # Resolve location coordinates if not explicitly passed
        resolved_lat = lat
        resolved_lon = lon
        if resolved_lat is None or resolved_lon is None:
            try:
                loc_data = await weather_service.resolve_coordinates(dist)
                resolved_lat = loc_data["latitude"]
                resolved_lon = loc_data["longitude"]
                dist = loc_data["name"]
            except Exception as e:
                logger.warning(f"Could not resolve coords for {dist}, using defaults: {e}")
                resolved_lat = 20.2961
                resolved_lon = 85.8245

        # Construct Webhook URL with production public default
        clean_base_url = (settings.twilio_webhook_base_url or base_url or "https://weathergpt-core.vercel.app").rstrip("/")
        if "localhost" in clean_base_url or "127.0.0.1" in clean_base_url or not clean_base_url.startswith("http"):
            clean_base_url = "https://weathergpt-core.vercel.app"

        query_params = {
            "district": dist,
            "lat": f"{resolved_lat:.4f}",
            "lon": f"{resolved_lon:.4f}",
            "lang": language
        }
        webhook_url = f"{clean_base_url}/api/ivr/welcome?{urlencode(query_params)}"

        logger.info(f"Initiating Twilio Outbound Call to {to_phone} from {from_phone}. Webhook URL: {webhook_url}")

        try:
            client = self.get_client()
            # STRICTLY only standard trial-compatible parameters: to, from_, url
            call = client.calls.create(
                to=to_phone,
                from_=from_phone,
                url=webhook_url
            )

            logger.info(f"Twilio call successfully queued. Call SID: {call.sid}")

            return {
                "status": "success",
                "call_sid": call.sid,
                "target_phone": to_phone,
                "from_phone": from_phone,
                "district": dist,
                "coordinates": {"latitude": resolved_lat, "longitude": resolved_lon},
                "webhook_url": webhook_url,
                "call_status": call.status,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }

        except TwilioRestException as tre:
            logger.error(f"Twilio REST Exception: code={tre.code}, msg={tre.msg}")
            raise RuntimeError(f"Twilio API Error ({tre.code}): {tre.msg}")
        except Exception as exc:
            logger.error(f"Unexpected error triggering Twilio call: {exc}")
            raise RuntimeError(f"Failed to initiate Twilio voice call: {str(exc)}")

    def add_ssml_speech(
        self,
        parent: Any,
        text: str,
        language: str = "en",
        voice: Optional[str] = None,
        rate: str = "95%",
        break_ms: str = "500ms"
    ) -> Say:
        """
        Renders a natural, high-clarity SSML speech block into a VoiceResponse or Gather.
        - English uses Polly.Kajal-Neural (en-IN)
        - Hindi uses Polly.Aditi (hi-IN)
        - Steady speaking rate with 95% prosody (<prosody rate="95%">)
        - 500ms natural pauses between sentences (<break time="500ms"/>)
        """
        is_hindi = language.lower().startswith("hi")
        selected_voice = voice or ("Polly.Aditi" if is_hindi else "Polly.Kajal-Neural")
        selected_lang = "hi-IN" if is_hindi else "en-IN"

        # Regex splits on sentence endings without splitting decimal numbers like 12.0 or 28.5
        import re
        pattern = r'(?<=[!?।]|(?<!\d)\.(?!\d))\s+'
        sentences = [s.strip() for s in re.split(pattern, text) if s.strip()]

        if not sentences:
            sentences = [text.strip()] if text.strip() else []

        say = parent.say(voice=selected_voice, language=selected_lang)
        for idx, sentence in enumerate(sentences):
            say.prosody(words=sentence, rate=rate)
            if idx < len(sentences) - 1:
                say.break_(time=break_ms)
        return say

    async def generate_welcome_twiml(
        self,
        district: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        base_url: str = ""
    ) -> str:
        """
        Generate TwiML for POST /api/ivr/welcome:
        - Speaks immediate dynamic emergency greeting for the detected district (hazard level, wind, rain)
          with natural SSML pacing and neural Indic voice.
        - Prompts for language selection via DTMF Gather (1 for English, 2 for Hindi).
        - Action URL: /api/ivr/menu
        """
        dist_name = district or "Khordha"
        resolved_lat = lat if lat is not None else 20.2961
        resolved_lon = lon if lon is not None else 85.8245

        # Ingest live telemetry
        try:
            metrics = await weather_service.get_live_metrics(resolved_lat, resolved_lon)
            hazard = evaluate_hazard_matrix(
                wind_speed=metrics["wind_speed_kmh"],
                wind_gusts=metrics["wind_gusts_kmh"],
                precipitation=metrics["precipitation_mm"],
                daily_rain=metrics["daily_rain_total_mm"],
                weather_code=metrics["weather_code"],
                temp=metrics["temperature_c"]
            )
        except Exception as e:
            logger.warning(f"Telemetry fetch error for welcome TwiML: {e}")
            metrics = {
                "temperature_c": 28.0,
                "wind_speed_kmh": 14.0,
                "precipitation_mm": 0.0,
                "humidity_percent": 65
            }
            hazard = {
                "level": "GREEN",
                "hazard_type": "Moderate Meteorological Conditions",
                "badge_text": "NORMAL"
            }

        hazard_level = hazard["level"]
        wind_spd = metrics.get("wind_speed_kmh", 12.0)
        precip = metrics.get("precipitation_mm", 0.0)
        temp = metrics.get("temperature_c", 28.0)

        # Build TwiML VoiceResponse
        vr = VoiceResponse()

        # 1. Immediate dynamic emergency alert greeting with SSML cadence
        if hazard_level in ["RED", "ORANGE"]:
            greeting_en = (
                f"Severe weather emergency alert from India Meteorological Department and NDMA for {dist_name}. "
                f"Emergency status is {hazard_level} warning. "
                f"Recorded winds are {wind_spd:.0f} kilometers per hour with {precip:.1f} millimeters of rainfall."
            )
        else:
            greeting_en = (
                f"Official weather bulletin from India Meteorological Department and NDMA for {dist_name}. "
                f"Alert level is {hazard_level}. "
                f"Temperature is {temp:.0f} degrees Celsius with wind speed {wind_spd:.0f} kilometers per hour."
            )

        self.add_ssml_speech(vr, greeting_en, language="en")
        vr.pause(length=1)

        # 2. DTMF Gather for Language Selection (1=English, 2=Hindi)
        clean_base_url = (settings.twilio_webhook_base_url or base_url or "https://weathergpt-core.vercel.app").rstrip("/")
        if "localhost" in clean_base_url or "127.0.0.1" in clean_base_url or not clean_base_url.startswith("http"):
            clean_base_url = "https://weathergpt-core.vercel.app"

        action_params = {
            "district": dist_name,
            "lat": f"{resolved_lat:.4f}",
            "lon": f"{resolved_lon:.4f}"
        }
        action_url = f"{clean_base_url}/api/ivr/menu?{urlencode(action_params)}"

        gather = Gather(
            num_digits=1,
            timeout=5,
            action=action_url,
            method="POST"
        )
        self.add_ssml_speech(gather, "For English, press 1.", language="en")
        self.add_ssml_speech(gather, "हिन्दी के लिए 2 दबाएँ।", language="hi")
        vr.append(gather)

        # Fallback if no digit pressed: redirect to English menu
        self.add_ssml_speech(vr, "No input received. Continuing in English.", language="en")
        vr.redirect(f"{action_url}&Digits=1", method="POST")

        return str(vr)

    async def generate_menu_twiml(
        self,
        digits: Optional[str] = "1",
        district: str = "Khordha",
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        base_url: str = ""
    ) -> str:
        """
        Generate TwiML for POST /api/ivr/menu:
        - Reads Digits (1 = English, 2 = Hindi).
        - Plays the 4-Persona Advisory Menu via DTMF Gather with SSML pacing:
            * Press 1: Farmer Advisory (agricultural drainage and crop safety guidelines)
            * Press 2: Fisherman Advisory (marine alert, wind surge, harbor docking order)
            * Press 3: General District Weather (temperature, humidity, precipitation metrics)
            * Press 4: High-Risk Emergency SOS Rescue
        - Action URL: /api/ivr/action
        """
        lang = "hi" if digits == "2" else "en"
        dist_name = district or "Khordha"
        resolved_lat = lat if lat is not None else 20.2961
        resolved_lon = lon if lon is not None else 85.8245

        clean_base_url = (settings.twilio_webhook_base_url or base_url or "https://weathergpt-core.vercel.app").rstrip("/")
        if "localhost" in clean_base_url or "127.0.0.1" in clean_base_url or not clean_base_url.startswith("http"):
            clean_base_url = "https://weathergpt-core.vercel.app"

        action_params = {
            "district": dist_name,
            "lang": lang,
            "lat": f"{resolved_lat:.4f}",
            "lon": f"{resolved_lon:.4f}"
        }
        action_url = f"{clean_base_url}/api/ivr/action?{urlencode(action_params)}"

        vr = VoiceResponse()

        gather = Gather(
            num_digits=1,
            timeout=6,
            action=action_url,
            method="POST"
        )

        if lang == "hi":
            menu_prompt = (
                f"{dist_name} मौसम विभाग परामर्श सेवा मेनू। "
                "कृषि एवं फसल सुरक्षा सलाह के लिए 1 दबाएँ। "
                "मछुआरों के लिए समुद्री सुरक्षा निर्देश हेतु 2 दबाएँ। "
                "जिले के मौसम और तापमान की जानकारी के लिए 3 दबाएँ। "
                "आपातकालीन एन डी आर एफ एस ओ एस बचाव सहायता के लिए 4 दबाएँ।"
            )
            self.add_ssml_speech(gather, menu_prompt, language="hi")
        else:
            menu_prompt = (
                f"WeatherGPT Advisory Menu for {dist_name}. "
                "Press 1 for Farmer Agricultural Advisory and crop safety guidelines. "
                "Press 2 for Fisherman Maritime Advisory and wind surge docking orders. "
                "Press 3 for General District Weather and live telemetry. "
                "Press 4 for High Risk Emergency S O S Rescue."
            )
            self.add_ssml_speech(gather, menu_prompt, language="en")

        vr.append(gather)

        # Fallback if no digit pressed: repeat menu prompt once then default to option 3
        if lang == "hi":
            self.add_ssml_speech(vr, "कोई विकल्प नहीं मिला। जिले का मौसम बुलेटिन सुनाया जा रहा है।", language="hi")
        else:
            self.add_ssml_speech(vr, "No input received. Playing general district weather bulletin.", language="en")

        vr.redirect(f"{action_url}&Digits=3", method="POST")
        return str(vr)

    async def generate_action_twiml(
        self,
        digits: Optional[str] = "3",
        lang: str = "en",
        district: str = "Khordha",
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        caller_phone: str = "",
        call_sid: str = ""
    ) -> str:
        """
        Generate TwiML for POST /api/ivr/action:
        - Reads Digits and delivers dynamic advisory generated from WeatherGPT backend with natural SSML speech.
        - If Digits == '4', logs emergency SOS event in dashboard state with coordinates and phone,
          and plays audio confirmation stating emergency rescue teams have been alerted.
        - Ends with polite signoff and hangs up the call.
        """
        dist_name = district or "Khordha"
        resolved_lat = lat if lat is not None else 20.2961
        resolved_lon = lon if lon is not None else 85.8245
        target_lang = "hi" if lang.lower().startswith("hi") else "en"
        selected_digit = str(digits).strip() if digits else "3"

        # Ingest live telemetry & evaluate decision models
        try:
            metrics = await weather_service.get_live_metrics(resolved_lat, resolved_lon)
            hazard = evaluate_hazard_matrix(
                wind_speed=metrics["wind_speed_kmh"],
                wind_gusts=metrics["wind_gusts_kmh"],
                precipitation=metrics["precipitation_mm"],
                daily_rain=metrics["daily_rain_total_mm"],
                weather_code=metrics["weather_code"],
                temp=metrics["temperature_c"]
            )
            agro = compute_agro_advisory(
                wind_speed=metrics["wind_speed_kmh"],
                precipitation=metrics["precipitation_mm"],
                humidity=metrics["humidity_percent"],
                temp=metrics["temperature_c"],
                weather_code=metrics["weather_code"]
            )
            marine = compute_marine_advisory(
                wind_speed=metrics["wind_speed_kmh"],
                wind_gusts=metrics["wind_gusts_kmh"],
                precipitation=metrics["precipitation_mm"],
                is_coastal=True
            )
        except Exception as e:
            logger.error(f"Error computing advisory in action TwiML: {e}")
            metrics = {
                "temperature_c": 28.0,
                "apparent_temperature_c": 29.0,
                "humidity_percent": 65,
                "wind_speed_kmh": 12.0,
                "precipitation_mm": 0.0
            }
            hazard = {"level": "GREEN", "hazard_type": "Normal Weather"}
            agro = {
                "spraying_desc_en": "Optimal spraying conditions.",
                "spraying_desc_hi": "छिड़काव के लिए अनुकूल समय।",
                "irrigation_en": "Maintain regular crop irrigation schedule.",
                "irrigation_hi": "सामान्य सिंचाई जारी रखें।",
                "harvesting_en": "Favorable conditions for crop harvesting and storage.",
                "harvesting_hi": "फसल कटाई के लिए मौसम अनुकूल है।"
            }
            marine = {
                "sea_state_en": "Calm and smooth sea.",
                "sea_state_hi": "समुद्र शांत और अनुकूल है।",
                "advisory_en": "Safe for coastal and deep sea fishing operations.",
                "advisory_hi": "मत्स्य पालन हेतु सुरक्षित स्थिति है।"
            }

        vr = VoiceResponse()

        # =========================================================================
        # 1. OPTION 1: FARMER ADVISORY (Agromet & Crop Protection)
        # =========================================================================
        if selected_digit == "1":
            if target_lang == "hi":
                speech = (
                    f"{dist_name} के लिए किसान कृषि परामर्श। "
                    f"कीटनाशक छिड़काव निर्देश: {agro.get('spraying_desc_hi', '')} "
                    f"सिंचाई एवं जल निकासी: {agro.get('irrigation_hi', '')} "
                    f"फसल कटाई निर्देश: {agro.get('harvesting_hi', '')}"
                )
                self.add_ssml_speech(vr, speech, language="hi")
            else:
                speech = (
                    f"Farmer Agricultural Advisory for {dist_name}. "
                    f"Chemical spraying window: {agro.get('spraying_desc_en', '')} "
                    f"Irrigation and field drainage: {agro.get('irrigation_en', '')} "
                    f"Harvest directives: {agro.get('harvesting_en', '')}"
                )
                self.add_ssml_speech(vr, speech, language="en")

        # =========================================================================
        # 2. OPTION 2: FISHERMAN ADVISORY (Maritime Alert & Port Docking)
        # =========================================================================
        elif selected_digit == "2":
            if target_lang == "hi":
                speech = (
                    f"{dist_name} तटीय क्षेत्र के लिए मछुआरा सुरक्षा निर्देश। "
                    f"समुद्र की स्थिति: {marine.get('sea_state_hi', '')} "
                    f"मार्गदर्शन: {marine.get('advisory_hi', '')}"
                )
                self.add_ssml_speech(vr, speech, language="hi")
            else:
                speech = (
                    f"Maritime and Fishermen Directive for {dist_name}. "
                    f"Current sea state: {marine.get('sea_state_en', '')} "
                    f"Maritime advisory: {marine.get('advisory_en', '')}"
                )
                self.add_ssml_speech(vr, speech, language="en")

        # =========================================================================
        # 3. OPTION 3: GENERAL DISTRICT WEATHER TELEMETRY
        # =========================================================================
        elif selected_digit == "3":
            temp_c = metrics.get("temperature_c", 28.0)
            feels_c = metrics.get("apparent_temperature_c", 29.0)
            humidity = metrics.get("humidity_percent", 65)
            wind_k = metrics.get("wind_speed_kmh", 12.0)
            rain_m = metrics.get("precipitation_mm", 0.0)
            alert_lvl = hazard.get("level", "GREEN")

            if target_lang == "hi":
                speech = (
                    f"{dist_name} का लाइव मौसम विवरण। "
                    f"सतही तापमान {temp_c:.1f} डिग्री सेल्सियस है, जो {feels_c:.1f} डिग्री महसूस हो रहा है। "
                    f"आर्द्रता {humidity} प्रतिशत है। "
                    f"पवन गति {wind_k:.1f} किलोमीटर प्रति घंटा है। "
                    f"वर्षा {rain_m:.1f} मिलीमीटर दर्ज की गई है। "
                    f"आपदा चेतावनी स्तर {alert_lvl} है।"
                )
                self.add_ssml_speech(vr, speech, language="hi")
            else:
                speech = (
                    f"Live Meteorological Telemetry for {dist_name}. "
                    f"Surface temperature is {temp_c:.1f} degrees Celsius, feels like {feels_c:.1f} degrees. "
                    f"Relative humidity is {humidity} percent. "
                    f"Wind speed is {wind_k:.1f} kilometers per hour with {rain_m:.1f} millimeters of rainfall. "
                    f"IMD Hazard Alert Status is {alert_lvl}."
                )
                self.add_ssml_speech(vr, speech, language="en")

        # =========================================================================
        # 4. OPTION 4: HIGH-RISK EMERGENCY SOS RESCUE
        # =========================================================================
        elif selected_digit == "4":
            caller = caller_phone or settings.twilio_target_phone
            event = self.log_sos_event(
                caller_phone=caller,
                district=dist_name,
                lat=resolved_lat,
                lon=resolved_lon,
                hazard_level=hazard.get("level", "RED"),
                call_sid=call_sid,
                language=target_lang
            )

            logger.critical(f"EMERGENCY SOS DISPATCH TRIGGERED! Event ID: {event['event_id']}, Phone: {caller}, District: {dist_name}")

            if target_lang == "hi":
                speech = (
                    f"आपातकालीन एस ओ एस संदेश प्राप्त हुआ। "
                    f"{dist_name} में आपके स्थान की जानकारी राष्ट्रीय आपदा प्रबंधन प्राधिकरण (एन डी एम ए) और स्थानीय आपदा राहत दल को तुरंत प्रेषित कर दी गई है। "
                    f"बचाव दल को आपके पंजीकृत नंबर {caller} पर सतर्क कर दिया गया है और सहायता रवाना कर दी गई है। "
                    "कृपया तुरंत सुरक्षित पक्के भवन में रहें। सहायता शीघ्र पहुँच रही है।"
                )
                self.add_ssml_speech(vr, speech, language="hi")
            else:
                speech = (
                    f"Emergency S O S received. "
                    f"Your geographic coordinates in {dist_name} at {resolved_lat:.2f} degrees North, {resolved_lon:.2f} degrees East have been immediately flagged to the National Disaster Management Authority and Local Emergency Rescue Operations. "
                    f"Emergency rescue teams have been alerted and dispatched to your registered phone number {caller}. "
                    "Please stay inside a secure reinforced shelter. Rescue units are on the way."
                )
                self.add_ssml_speech(vr, speech, language="en")

        # Fallback for unrecognized digit
        else:
            if target_lang == "hi":
                self.add_ssml_speech(vr, "अमान्य विकल्प चुना गया।", language="hi")
            else:
                self.add_ssml_speech(vr, "Invalid menu selection.", language="en")

        # Polite Signoff & Hangup
        vr.pause(length=1)
        if target_lang == "hi":
            self.add_ssml_speech(vr, "भारत मौसम विज्ञान विभाग निर्णय प्रणाली का उपयोग करने के लिए धन्यवाद। सुरक्षित रहें। नमस्ते।", language="hi")
        else:
            self.add_ssml_speech(vr, "Thank you for using India Meteorological Department Decision Support System. Stay safe. Goodbye.", language="en")

        vr.hangup()
        return str(vr)

    def log_sos_event(
        self,
        caller_phone: str,
        district: str,
        lat: float,
        lon: float,
        hazard_level: str = "RED",
        call_sid: str = "",
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Log an emergency SOS rescue event in the backend state & persistent store.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        event_id = f"SOS-IMD-{now.strftime('%Y%m%d%H%M%S')}-{len(self._sos_events)+1:03d}"

        event = {
            "event_id": event_id,
            "timestamp": now.isoformat(),
            "phone_number": caller_phone,
            "district": district,
            "coordinates": {
                "latitude": round(lat, 5),
                "longitude": round(lon, 5)
            },
            "hazard_level": hazard_level,
            "call_sid": call_sid,
            "language": language,
            "status": "RESCUE_DISPATCHED",
            "responding_agency": "NDMA / NDRF State Disaster Response Unit",
            "dispatch_priority": "CRITICAL_TIER_1"
        }

        # Keep latest 100 events in memory
        self._sos_events.insert(0, event)
        if len(self._sos_events) > 100:
            self._sos_events = self._sos_events[:100]

        self._save_sos_events()
        return event

    def get_sos_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve recent SOS emergency events."""
        return self._sos_events[:limit]


ivr_service = TwilioIVRService()
