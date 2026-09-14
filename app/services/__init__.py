"""
WeatherGPT Services Package
Contains asynchronous weather data ingestion, IMD/NDMA hazard rules, multilingual bulletin synthesis,
and Bhashini Speech-to-Speech (ASR & TTS) integration.
"""

from app.services.weather_service import weather_service, WeatherService, LocationNotFoundError
from app.services.hazard_engine import evaluate_hazard_matrix, compute_agro_advisory, compute_marine_advisory
from app.services.synthesizer import synthesize_bulletin, get_weather_description
from app.services.bhashini_service import bhashini_service, BhashiniService
from app.services.ivr_service import ivr_service, TwilioIVRService

__all__ = [
    "weather_service",
    "WeatherService",
    "LocationNotFoundError",
    "evaluate_hazard_matrix",
    "compute_agro_advisory",
    "compute_marine_advisory",
    "synthesize_bulletin",
    "get_weather_description",
    "bhashini_service",
    "BhashiniService",
    "ivr_service",
    "TwilioIVRService"
]

