"""
WeatherGPT - Ground-Truth Multilingual Synthesizer
Ministry of Earth Sciences (MoES / SIH26068)

Deterministically generates official administrative bulletins and TTS audio scripts
in English and Hindi (हिन्दी) without LLM hallucination risk.
"""

from typing import Dict, Any

# Official WMO (World Meteorological Organization) Code Interpretations
WMO_INTERPRETATIONS: Dict[int, Dict[str, str]] = {
    0: {"en": "Clear sky", "hi": "साफ़ आसमान", "icon": "sun"},
    1: {"en": "Mainly clear", "hi": "मुख्य रूप से साफ़", "icon": "sun-cloud"},
    2: {"en": "Partly cloudy", "hi": "आंशिक रूप से बादलमय", "icon": "cloud-sun"},
    3: {"en": "Overcast", "hi": "घने बादल", "icon": "cloud"},
    45: {"en": "Fog", "hi": "कोहरा", "icon": "fog"},
    48: {"en": "Depositing rime fog", "hi": "जमावदार कोहरा", "icon": "fog"},
    51: {"en": "Light drizzle", "hi": "हल्की बूंदाबांदी", "icon": "drizzle"},
    53: {"en": "Moderate drizzle", "hi": "मध्यम बूंदाबांदी", "icon": "drizzle"},
    55: {"en": "Dense drizzle", "hi": "सघन बूंदाबांदी", "icon": "drizzle"},
    61: {"en": "Slight rain", "hi": "हल्की वर्षा", "icon": "rain-light"},
    63: {"en": "Moderate rain", "hi": "मध्यम वर्षा", "icon": "rain"},
    65: {"en": "Heavy rain", "hi": "भारी वर्षा", "icon": "rain-heavy"},
    71: {"en": "Slight snow fall", "hi": "हल्का हिमपात", "icon": "snow"},
    73: {"en": "Moderate snow fall", "hi": "मध्यम हिमपात", "icon": "snow"},
    75: {"en": "Heavy snow fall", "hi": "भारी हिमपात", "icon": "snow"},
    80: {"en": "Slight rain showers", "hi": "हल्की बौछारें", "icon": "showers"},
    81: {"en": "Moderate rain showers", "hi": "मध्यम बौछारें", "icon": "showers"},
    82: {"en": "Violent rain showers", "hi": "तीव्र मूसलाधार बौछारें", "icon": "storm-heavy"},
    95: {"en": "Thunderstorm", "hi": "गरज के साथ तूफ़ान / तड़ित झंझा", "icon": "thunder"},
    96: {"en": "Thunderstorm with slight hail", "hi": "ओलावृष्टि के साथ तूफ़ान", "icon": "thunder-hail"},
    99: {"en": "Thunderstorm with heavy hail", "hi": "भारी ओलावृष्टि के साथ तीव्र तूफ़ान", "icon": "thunder-hail-heavy"},
}


def get_weather_description(weather_code: int, lang_code: str = "en") -> str:
    """Retrieve localized weather description from WMO interpretation table."""
    entry = WMO_INTERPRETATIONS.get(weather_code, WMO_INTERPRETATIONS[0])
    return entry.get(lang_code, entry.get("en", "Normal Sky"))


def synthesize_bulletin(
    location_data: Dict[str, Any],
    metrics: Dict[str, Any],
    hazard: Dict[str, Any],
    agro: Dict[str, Any],
    marine: Dict[str, Any],
    language: str = "en"
) -> Dict[str, Any]:
    """
    Synthesize high-fidelity administrative bulletins and TTS audio scripts
    based strictly on deterministic meteorological ground truth.
    """
    lang = language.lower()
    if lang in ["hi", "hindi"]:
        target_lang = "hi"
    else:
        target_lang = "en"

    temp = metrics.get("temperature_c", 25.0)
    apparent_temp = metrics.get("apparent_temperature_c", 26.0)
    humidity = metrics.get("humidity_percent", 60)
    wind_spd = metrics.get("wind_speed_kmh", 10.0)
    wind_dir = metrics.get("wind_direction_deg", 0)
    precip = metrics.get("precipitation_mm", 0.0)
    daily_rain = metrics.get("daily_rain_total_mm", 0.0)
    weather_code = metrics.get("weather_code", 0)

    place_name = location_data.get("name", "Unknown Location")
    state_name = location_data.get("state", "India")
    condition_text = get_weather_description(weather_code, target_lang)

    # 1. HINDI SYNTHESIS (हिन्दी)
    if target_lang == "hi":
        alert_title = hazard["title_hi"]
        alert_inst = hazard["instructions_hi"]
        agro_spray = agro["spraying_desc_hi"]
        agro_irr = agro["irrigation_hi"]
        agro_harv = agro.get("harvesting_hi", "")
        marine_adv = marine["advisory_hi"]
        marine_sea = marine["sea_state_hi"]

        narrative = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  भारत मौसम विज्ञान विभाग (IMD) / पृथ्वी विज्ञान मंत्रालय (MoES)\n"
            f"  आधिकारिक मौसम बुलेटिन एवं आपदा पूर्व-चेतावनी रिपोर्ट\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📍 वेधशाला केंद्र: {place_name} ({state_name})\n"
            f"🌡️ तापमान: {temp:.1f}°C (महसूस: {apparent_temp:.1f}°C) | 💧 सापेक्षिक आर्द्रता: {humidity}%\n"
            f"💨 सतही पवन: {wind_spd:.1f} km/h (दिशा: {wind_dir}°) | 🌧️ 24 घंटे की वर्षा: {precip:.1f} mm (कुल संचयी: {daily_rain:.1f} mm)\n"
            f"☁️ वर्तमान वायुमंडलीय स्थिति: {condition_text}\n\n"
            f"🚨 आपदा चेतावनी स्तर: {alert_title}\n"
            f"📌 प्रशासनिक निर्देश: {alert_inst}\n\n"
            f"🌾 कृषि मौसम परामर्श (Agro-Advisory):\n"
            f"  • कीटनाशक एवं पोषण छिड़काव: {agro_spray}\n"
            f"  • सिंचाई एवं जल प्रबंधन: {agro_irr}\n"
            f"  • फसल कटाई एवं भंडारण: {agro_harv}\n\n"
            f"⚓ तटीय एवं मछुआरा सुरक्षा निर्देश:\n"
            f"  • समुद्र की स्थिति: {marine_sea}\n"
            f"  • दिशा-निर्देश: {marine_adv}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"प्रमाणीकरण: भारत मौसम विज्ञान विभाग स्वायत्त निर्णय प्रणाली (SIH26068)"
        )

        tts_script = (
            f"{place_name} {state_name} के लिए भारत मौसम विज्ञान विभाग का आधिकारिक बुलेटिन। "
            f"वर्तमान तापमान {temp:.1f} डिग्री सेल्सियस है और स्थिति {condition_text} है। "
            f"आपदा चेतावनी स्तर {hazard['level']} है। {alert_inst} "
            f"कृषि सलाह: {agro_spray} {agro_irr} "
            f"मछुआरों के लिए निर्देश: {marine_adv}"
        )

    # 2. ENGLISH SYNTHESIS (Official Standard)
    else:
        alert_title = hazard["title_en"]
        alert_inst = hazard["instructions_en"]
        agro_spray = agro["spraying_desc_en"]
        agro_irr = agro["irrigation_en"]
        agro_harv = agro.get("harvesting_en", "")
        marine_adv = marine["advisory_en"]
        marine_sea = marine["sea_state_en"]

        narrative = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  INDIA METEOROLOGICAL DEPARTMENT (IMD) / MINISTRY OF EARTH SCIENCES\n"
            f"  OFFICIAL METEOROLOGICAL BULLETIN & EARLY-WARNING ADVISORY\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📍 Observatory Station: {place_name}, {state_name}\n"
            f"🌡️ Surface Temp: {temp:.1f}°C (Feels Like: {apparent_temp:.1f}°C) | 💧 Relative Humidity: {humidity}%\n"
            f"💨 Wind Velocity: {wind_spd:.1f} km/h (Azimuth: {wind_dir}°) | 🌧️ 24h Rainfall: {precip:.1f} mm (Cumulative: {daily_rain:.1f} mm)\n"
            f"☁️ Sky Condition: {condition_text}\n\n"
            f"🚨 Disaster Alert Status: {alert_title}\n"
            f"📌 Operational Directive: {alert_inst}\n\n"
            f"🌾 Agro-Meteorological Advisory (GKMS / ICAR Protocol):\n"
            f"  • Foliar/Pesticide Spray Window: {agro_spray}\n"
            f"  • Irrigation & Soil Drainage: {agro_irr}\n"
            f"  • Crop Harvest & Protection: {agro_harv}\n\n"
            f"⚓ Marine & Fishermen Directive (INCOIS / IMD Protocol):\n"
            f"  • Sea State: {marine_sea}\n"
            f"  • Maritime Clearance: {marine_adv}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Authority: Autonomous Meteorological Decision Support System (SIH26068)"
        )

        tts_script = (
            f"Official IMD meteorological bulletin for {place_name}, {state_name}. "
            f"Current surface temperature is {temp:.1f} degrees Celsius with {condition_text}. "
            f"Disaster alert level is {hazard['level']}. {alert_inst} "
            f"Agricultural directive: {agro_spray} {agro_irr} "
            f"Marine directive: {marine_adv}"
        )

    return {
        "language": target_lang,
        "condition_text": condition_text,
        "narrative": narrative,
        "tts_script": tts_script,
        "alert_title": alert_title,
        "alert_instructions": alert_inst
    }
