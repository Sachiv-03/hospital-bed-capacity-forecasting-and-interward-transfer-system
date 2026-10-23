from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class SourceCategory(str, Enum):
    CURRENT_AVAILABILITY = "CURRENT_AVAILABILITY"
    OCCUPANCY_TRENDS = "OCCUPANCY_TRENDS"
    SARIMA_FORECAST = "SARIMA_FORECAST"
    CAPACITY_RISK_ALERTS = "CAPACITY_RISK_ALERTS"
    TRANSFER_DECISION_SUPPORT = "TRANSFER_DECISION_SUPPORT"
    MANAGEMENT_SUMMARY = "MANAGEMENT_SUMMARY"
    GENERAL_HELP = "GENERAL_HELP"


class ConversationMessage(BaseModel):
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., max_length=10000, description="Message text")
    timestamp: Optional[str] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in [MessageRole.USER.value, MessageRole.ASSISTANT.value, MessageRole.SYSTEM.value]:
            raise ValueError(f"Invalid role: {v}. Must be 'user' or 'assistant'.")
        return clean

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        # Gracefully handle string content and trim if exceeding bounds
        if not v:
            return ""
        return v[:10000]


class AssistantQueryRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User question in natural language (1-1000 characters)",
    )
    conversation_history: Optional[List[ConversationMessage]] = Field(
        default_factory=list,
        description="Recent session history (max 8 messages sent for context)",
    )
    hospital_id: Optional[int] = Field(
        None,
        description="Hospital ID override (authorized for SUPER_ADMIN only)",
    )
    ward_id: Optional[int] = Field(
        None,
        description="Optional ward identifier to scope query",
    )

    @field_validator("message")
    @classmethod
    def validate_message_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message cannot be empty or purely whitespace")
        if len(stripped) > 1000:
            raise ValueError("String should have at most 1000 characters")
        return stripped

    @field_validator("conversation_history")
    @classmethod
    def limit_history_length(cls, v: Optional[List[ConversationMessage]]) -> List[ConversationMessage]:
        if not v:
            return []
        # Retain only the latest 8 messages to prevent context exhaustion
        return v[-8:]


class AssistantQueryResponse(BaseModel):
    answer: str = Field(..., description="Conversational explanation grounded in verified backend evidence")
    source_category: str = Field(..., description="Primary data domain category")
    evidence: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured verified metrics used to generate the answer",
    )
    data_timestamp: Optional[str] = Field(
        None,
        description="Timestamp of the underlying data source (live or historical)",
    )
    is_forecast_estimate: bool = Field(
        False,
        description="True if the response references forward-looking statistical predictions",
    )
    forecast_target_date: Optional[str] = Field(
        None,
        description="Target projection date for forecasts, if applicable",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Data caveats, missing observations, or provider notices",
    )
    provider_status: str = Field(
        ...,
        description="Active reasoning provider ('live_gemini', 'live_openai', 'mock_deterministic')",
    )
    suggested_followups: List[str] = Field(
        default_factory=list,
        description="Contextual follow-up suggestions for hospital management staff",
    )


class AssistantStatusResponse(BaseModel):
    enabled: bool
    provider: str
    model: str
    has_api_key: bool
    supported_categories: List[str]
    disclaimer: str
