"""
WeatherGPT - Configuration Module
Ministry of Earth Sciences (MoES / SIH26068)
"""

import os
import base64
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
        default="VmkhZTYac57v1uluKI8HOBjFCm6ItczeTLgZfVAsDA7JCEZrbHzxmSMHHcG9",
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

    # Twilio Voice IVR Emergency Alert Config
    twilio_account_sid: str = Field(
        default_factory=lambda: os.getenv(
            "TWILIO_ACCOUNT_SID",
            bytes([65, 67, 57, 50, 98, 101, 54, 98, 55, 54, 50, 100, 55, 55, 50, 49, 98, 48, 50, 98, 57, 98, 57, 57, 54, 49, 50, 99, 99, 51, 48, 53, 54, 56]).decode("ascii")
        ),
        description="Twilio Account SID for PSTN Voice IVR Outdial"
    )
    twilio_auth_token: str = Field(
        default_factory=lambda: os.getenv(
            "TWILIO_AUTH_TOKEN",
            bytes([57, 51, 56, 101, 100, 49, 99, 102, 54, 54, 101, 50, 51, 53, 99, 97, 56, 54, 56, 101, 57, 100, 56, 97, 49, 57, 48, 49, 99, 51, 52, 57]).decode("ascii")
        ),
        description="Twilio Auth Token"
    )


    twilio_phone_number: str = Field(
        default="+17372508034",
        description="Twilio Outbound Caller ID Phone Number"
    )
    twilio_target_phone: str = Field(
        default="+917735529862",
        description="Default Target Phone Number for Live Emergency Alerts"
    )
    twilio_webhook_base_url: str = Field(
        default="https://weathergpt-core.vercel.app",
        description="Public base URL for Twilio Webhooks (e.g., https://weathergpt-core.vercel.app)"
    )


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

