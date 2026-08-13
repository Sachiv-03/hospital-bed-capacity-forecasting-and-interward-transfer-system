import json
from typing import List, Union
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

    # Stage 2 — Automated Occupancy Snapshot & Capacity Alerts
    SNAPSHOT_ENABLED: bool = True
    SNAPSHOT_INTERVAL_SECONDS: int = 300
    ALERT_HIGH_THRESHOLD: float = 85.0
    ALERT_CRITICAL_THRESHOLD: float = 95.0
    ALERT_LOW_AVAILABILITY_THRESHOLD: int = 2


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
