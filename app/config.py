"""
WeatherGPT - Configuration Module
Ministry of Earth Sciences (MoES / SIH26068)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings and meteorological endpoint configuration."""

    # Project Metadata
    app_name: str = "WeatherGPT - MoES Early Warning & Decision Support System"
    app_version: str = "2.0.0"
    app_description: str = "Ministry of Earth Sciences (MoES) SIH26068 Meteorological Advisory Engine"
    sih_track: str = "SIH26068 - Ministry of Earth Sciences"

    # API & Network Config
    http_timeout_seconds: float = Field(default=8.0, description="HTTP request timeout in seconds")
    max_retries: int = Field(default=2, description="Maximum retry attempts for meteorological endpoints")

    # Public Meteorological Endpoints
    geocoding_api_url: str = Field(
        default="https://geocoding-api.open-meteo.com/v1/search",
        description="Open-Meteo Dynamic Geocoding endpoint"
    )
    weather_api_url: str = Field(
        default="https://api.open-meteo.com/v1/forecast",
        description="Open-Meteo High-Resolution Numerical Weather Telemetry endpoint"
    )

    # Telemetry Cache Settings
    cache_ttl_seconds: int = Field(
        default=300,
        description="In-memory cache time-to-live for meteorological telemetry (5 minutes)"
    )

    # Bhashini Speech-to-Speech (ASR & TTS) Pipeline Config
    bhashini_user_id: str = Field(
        default="",
        description="Bhashini (ULCA) User ID / ULCA ID"
    )
    bhashini_api_key: str = Field(
        default="",
        description="Bhashini API Key / Ingestion Auth Key"
    )
    bhashini_pipeline_id: str = Field(
        default="",
        description="Bhashini Pipeline ID for ASR & TTS inference"
    )
    bhashini_inference_url: str = Field(
        default="https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
        description="Bhashini Dhruva Pipeline Inference endpoint"
    )
    bhashini_timeout_seconds: float = Field(
        default=12.0,
        description="HTTP request timeout for Bhashini pipeline requests in seconds"
    )

    # Fast2SMS Live Telecom SMS Gateway Config
    fast2sms_api_key: str = Field(
        default="ynaovNqH5JTOLY36fVbX2dDueIx1kwzSB40Eh8rMKR71psPjUZCI8gsN53F4nHefm0aYXQTVypDZMKi",
        description="Fast2SMS Authorization / API Key for live physical SMS dispatch"
    )
    fast2sms_api_url: str = Field(
        default="https://www.fast2sms.com/dev/bulkV2",
        description="Fast2SMS Bulk V2 POST Endpoint"
    )
    fast2sms_timeout_seconds: float = Field(
        default=12.0,
        description="HTTP request timeout for Fast2SMS gateway requests in seconds"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
