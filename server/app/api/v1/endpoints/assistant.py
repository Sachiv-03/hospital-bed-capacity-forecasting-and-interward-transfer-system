import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db, require_roles
from app.core.config import settings
from app.models.user import User, UserRole
from app.schemas.assistant import (
    AssistantQueryRequest,
    AssistantQueryResponse,
    AssistantStatusResponse,
    SourceCategory,
)
from app.services.ai.assistant_service import AssistantService

logger = logging.getLogger(__name__)

router = APIRouter()

ALL_AUTHORIZED_ROLES = [
    UserRole.SUPER_ADMIN.value,
    UserRole.ADMIN.value,
    UserRole.DOCTOR.value,
    UserRole.NURSE.value,
    UserRole.RECEPTIONIST.value,
]


def resolve_hospital_scope(current_user: User, requested_hospital_id: Optional[int]) -> int:
    """Enforce hospital-level tenant isolation."""
    if current_user.role == UserRole.SUPER_ADMIN.value:
        return requested_hospital_id or current_user.hospital_id or 1

    if current_user.hospital_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is not associated with any hospital facility.",
        )

    if requested_hospital_id is not None and requested_hospital_id != current_user.hospital_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cross-hospital access forbidden. You cannot access hospital ID {requested_hospital_id}.",
        )

    return current_user.hospital_id


@router.post(
    "/query",
    response_model=AssistantQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query AI Hospital Management Assistant",
    description="Submits a natural-language hospital management question, retrieves verified backend data, and explains it with conversational AI.",
)
def query_assistant(
    request: AssistantQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ALL_AUTHORIZED_ROLES)),
):
    if not settings.AI_ASSISTANT_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Hospital Management Assistant is currently disabled in system configuration.",
        )

    hospital_id = resolve_hospital_scope(current_user, request.hospital_id)

    try:
        return AssistantService.handle_query(
            db=db,
            request=request,
            hospital_id=hospital_id,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Assistant processing error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing your request: {str(e)}",
        )


@router.get(
    "/status",
    response_model=AssistantStatusResponse,
    summary="Get AI Assistant Operational Status",
    description="Returns configuration status, active reasoning provider, model identifier, and supported capabilities.",
)
def get_assistant_status(
    current_user: User = Depends(get_current_active_user),
):
    has_gemini = bool(settings.GEMINI_API_KEY)
    has_openai = bool(settings.OPENAI_API_KEY)
    has_api_key = has_gemini or has_openai

    provider_name = settings.LLM_PROVIDER
    if provider_name == "auto":
        provider_name = "gemini" if has_gemini else ("openai" if has_openai else "mock")

    model_name = settings.GEMINI_MODEL if provider_name == "gemini" else (
        settings.OPENAI_MODEL if provider_name == "openai" else "deterministic-synthesizer"
    )

    return AssistantStatusResponse(
        enabled=settings.AI_ASSISTANT_ENABLED,
        provider=provider_name,
        model=model_name,
        has_api_key=has_api_key,
        supported_categories=[c.value for c in SourceCategory],
        disclaimer="AI Hospital Management Assistant provides decision support based on backend telemetry and SARIMA forecasts. It does not execute transfers or replace clinical judgment.",
    )
