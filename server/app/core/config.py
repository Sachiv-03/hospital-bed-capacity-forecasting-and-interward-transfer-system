import json
from typing import List, Union, Optional
from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Powered Hospital Bed Capacity Forecasting & Intelligent Inter-Ward Transfer System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Database (Neon PostgreSQL Cloud Connection)
    DATABASE_URL: str = "postgresql://neondb_owner:YOUR_PASSWORD@ep-sample-123456.us-east-2.aws.neon.tech/neondb?sslmode=require"

    # Security
    SECRET_KEY: str = "dev_secret_key_change_in_production_hospital_bed_system_987654321"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Phase 6 — Hospital Simulator (development only)
    SIMULATOR_ENABLED: bool = False
    SIMULATOR_INTERVAL_SECONDS: int = 10
    SIMULATOR_HOSPITAL_ID: int = 1

    # Stage 2 & Explainable AI Alerts Configuration
    # NOTE: Configured thresholds are operational demonstration defaults and require approval
    # by authorized hospital administrators before operational use.
    SNAPSHOT_ENABLED: bool = True
    SNAPSHOT_INTERVAL_SECONDS: int = 300
    ALERT_MODERATE_THRESHOLD: float = 70.0
    ALERT_HIGH_THRESHOLD: float = 85.0
    ALERT_CRITICAL_THRESHOLD: float = 95.0
    ALERT_LOW_AVAILABILITY_THRESHOLD: int = 2
    ALERT_RAPID_INCREASE_THRESHOLD: float = 15.0  # Percentage point increase over recent window
    ALERT_RAPID_INCREASE_DAYS: int = 3           # Days to measure recent occupancy velocity
    ALERT_UNCERTAINTY_THRESHOLD: float = 25.0    # CI width (upper_bound - lower_bound %) indicating high uncertainty
    ALERT_FORECAST_HORIZON_DAYS: int = 7         # Default forecast horizon evaluated for capacity risk

    # Stage 3 — Bed Capacity Forecasting
    FORECAST_ENABLED: bool = True
    FORECAST_INTERVAL_SECONDS: int = 86400  # Default 24 hours (configurable for dev)
    FORECAST_MIN_OBSERVATIONS: int = 7       # Minimum daily snapshot observations for forecasting
    FORECAST_NORMAL_THRESHOLD: float = 70.0
    FORECAST_MODERATE_THRESHOLD: float = 85.0
    FORECAST_HIGH_THRESHOLD: float = 95.0

    # Phase 17 — AI Hospital Management Assistant
    AI_ASSISTANT_ENABLED: bool = True
    LLM_PROVIDER: str = "auto"  # "auto", "gemini", "openai", "mock"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    LLM_REQUEST_TIMEOUT_SECONDS: int = 20
    LLM_MAX_TOKENS: int = 1024
    LLM_TEMPERATURE: float = 0.2
    AI_MAX_MESSAGE_LENGTH: int = 1000
    AI_MAX_HISTORY_MESSAGES: int = 8


    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]

    @validator("CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, str):
            return json.loads(v)
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
